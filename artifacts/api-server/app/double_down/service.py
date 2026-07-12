from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib import parse
from uuid import UUID

from app.double_down.demo_execution import (
    DemoChallengeExecutor,
    DemoExecutionIntent,
)
from app.double_down.engine import ChallengeEngine
from app.double_down.enums import (
    ChallengeDirection,
    ChallengeExchangeMode,
    ChallengeSlotType,
    ChallengeStatus,
)
from app.double_down.market_data import (
    ChallengeTicker,
    ClosedCandle,
    select_challenge_slots,
)
from app.double_down.persistence import ChallengePersistence
from app.double_down.risk import (
    InstrumentSizingRules,
    size_challenge_position,
)
from app.double_down.schemas import ChallengeConfig, ChallengeLedgerEntry, ChallengeState
from app.double_down.strategy import evaluate_momentum_volume_strategy


class ChallengeExchangeTransport:
    def __init__(self, bybit_service) -> None:
        self._bybit_service = bybit_service

    def place_market_order(self, payload: dict[str, str]) -> dict:
        order = self._bybit_service.create_private_order(
            {
                "category": "linear",
                "symbol": payload["symbol"],
                "side": payload["side"],
                "orderType": payload.get("orderType", "Market"),
                "qty": payload["qty"],
                "timeInForce": "IOC",
                "positionIdx": 0,
                "orderLinkId": payload["clientOrderId"],
                "reduceOnly": payload.get("reduceOnly", "false") == "true",
            }
        )
        order_id = order.get("result", {}).get("orderId")
        return {
            "accepted": bool(order_id),
            "order_id": str(order_id or ""),
            "message": order.get("retMsg") or "accepted",
        }

    def attach_protection(self, payload: dict[str, str]) -> dict:
        self._bybit_service._private_post(
            "/v5/position/trading-stop",
            {
                "category": "linear",
                "symbol": payload["symbol"],
                "tpslMode": "Full",
                "positionIdx": 0,
                "stopLoss": payload["stopLoss"],
                "takeProfit": payload["takeProfit"],
                "slTriggerBy": "MarkPrice",
                "tpTriggerBy": "MarkPrice",
            },
        )
        position = self.get_position(symbol=payload["symbol"])
        return {
            "accepted": True,
            "confirmed": bool(position and position.get("protected")),
            "message": "protection_attached",
        }

    def get_order(self, *, symbol: str, client_order_id: str) -> dict | None:
        rows = self._bybit_service.get_order_history(
            symbol=symbol,
            order_link_id=client_order_id,
            limit=5,
        )
        if not rows:
            return None
        row = rows[0]
        position = self.get_position(symbol=symbol)
        return {
            "order_id": str(row.get("orderId") or ""),
            "protected": bool(position and position.get("protected")),
        }

    def get_position(self, *, symbol: str) -> dict | None:
        position = self._bybit_service.get_position(symbol)
        if not position:
            return None
        stop_loss = str(position.get("stopLoss") or "").strip()
        take_profit = str(position.get("takeProfit") or "").strip()
        return {
            "order_id": str(position.get("positionIdx") or "0"),
            "protected": bool(stop_loss and take_profit and stop_loss != "0" and take_profit != "0"),
        }

    def emergency_close(self, payload: dict[str, str]) -> dict:
        order = self._bybit_service.emergency_close_position(
            symbol=payload["symbol"],
            side=payload["side"],
            qty=payload["qty"],
            order_link_id=payload["clientOrderId"],
        )
        order_id = order.get("result", {}).get("orderId")
        return {"accepted": bool(order_id), "order_id": str(order_id or "")}


class ChallengeService:
    def __init__(self, persistence: ChallengePersistence, bybit_service=None) -> None:
        self._persistence = persistence
        self._bybit_service = bybit_service
        self._engines: dict[UUID, ChallengeEngine] = {}
        self._runtime: dict[UUID, dict[str, Any]] = {}

    def create(self, *, starting_balance: Decimal, failure_floor: Decimal) -> dict:
        engine = ChallengeEngine.create(
            starting_balance=starting_balance,
            failure_floor=failure_floor,
        )
        engine.mark_ready()
        challenge_id = engine.config.challenge_id
        self._runtime[challenge_id] = self._default_runtime()
        try:
            snapshot = self._save(engine)
        except Exception:
            self._runtime.pop(challenge_id, None)
            raise
        self._engines[engine.config.challenge_id] = engine
        return snapshot

    def get(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        return self._build_payload(engine)

    def list(self) -> list[dict]:
        snapshots = [self._build_payload(engine) for engine in self._engines.values()]
        persisted = self._persistence.list_snapshots()
        seen = {item["config"]["challenge_id"] for item in snapshots}
        snapshots.extend(
            item for item in persisted
            if item.get("config", {}).get("challenge_id") not in seen
        )
        return snapshots

    def start(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        previous = self._snapshot_copy(engine, challenge_id)
        engine.start()
        return self._save_with_rollback(engine, previous)

    def pause(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        previous = self._snapshot_copy(engine, challenge_id)
        engine.pause()
        return self._save_with_rollback(engine, previous)

    def resume(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        previous = self._snapshot_copy(engine, challenge_id)
        engine.resume()
        return self._save_with_rollback(engine, previous)

    def terminate(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        previous = self._snapshot_copy(engine, challenge_id)
        engine.terminate()
        runtime = self._runtime.setdefault(challenge_id, self._default_runtime())
        runtime["active_cycle"] = None
        return self._save_with_rollback(engine, previous)

    def run_cycle(self, challenge_id: UUID) -> dict:
        if self._bybit_service is None:
            raise RuntimeError("Challenge execution wiring is unavailable.")
        engine = self._get_engine(challenge_id)
        if engine.state.status not in {ChallengeStatus.RUNNING, ChallengeStatus.RECOVERY}:
            raise ValueError("challenge must be running or recovery before cycle execution")
        runtime = self._runtime.setdefault(challenge_id, self._default_runtime())
        if runtime.get("active_cycle") is not None or engine.state.active_trade_count > 0:
            raise ValueError("challenge already has an active cycle")

        previous = self._snapshot_copy(engine, challenge_id)
        selections = select_challenge_slots(self._load_market_tickers())
        decision_rows = []
        approved_decisions = []
        for selection in selections:
            candles = self._load_recent_candles(selection.symbol)
            decision = evaluate_momentum_volume_strategy(
                slot_type=selection.slot_type,
                candles=candles,
            )
            row = {
                "slot_type": selection.slot_type.value,
                "symbol": selection.symbol,
                "reason": selection.reason,
                "strategy": decision.strategy_name,
                "approved": decision.approved,
                "direction": decision.direction.value if decision.direction else None,
                "confidence": str(decision.confidence),
                "rejection_code": decision.rejection_code,
                "evidence": dict(decision.evidence),
            }
            decision_rows.append(row)
            if decision.approved:
                approved_decisions.append((decision, row))

        if not approved_decisions:
            runtime["active_cycle"] = None
            runtime["last_cycle"] = {
                "planned_at": datetime.now(timezone.utc).isoformat(),
                "status": "no_approved_slots",
                "selected_slots": decision_rows,
                "approved_slots": [],
                "execution_results": [],
                "finalization": None,
            }
            return self._save_with_rollback(engine, previous)

        sized_decisions = []
        for decision, row in approved_decisions:
            size = size_challenge_position(
                current_balance=engine.state.current_balance,
                approved_slots=len(approved_decisions),
                decision=decision,
                instrument=self._instrument_rules(decision.symbol),
            )
            sized_decisions.append((decision, size, row))

        executable = []
        for decision, size, row in sized_decisions:
            row["size_approved"] = size.approved
            row["size_rejection_code"] = size.rejection_code
            row["size_evidence"] = dict(size.evidence)
            if size.approved:
                executable.append((decision, size, row))

        if not executable:
            runtime["active_cycle"] = None
            runtime["last_cycle"] = {
                "planned_at": datetime.now(timezone.utc).isoformat(),
                "status": "no_executable_positions",
                "selected_slots": decision_rows,
                "approved_slots": [],
                "execution_results": [],
                "finalization": None,
            }
            return self._save_with_rollback(engine, previous)

        plan = engine.plan_cycle(len(executable))
        engine.activate_cycle(len(executable))
        executor = DemoChallengeExecutor(ChallengeExchangeTransport(self._bybit_service))
        execution_results: list[dict[str, Any]] = []
        active_trades: list[dict[str, Any]] = []
        immediate_adjustment = Decimal("0")

        for decision, size, row in executable:
            slot_key = ChallengeSlotType(row["slot_type"]).value
            intent = DemoExecutionIntent(
                challenge_id=str(engine.config.challenge_id),
                cycle_number=engine.state.cycle_number,
                slot_key=slot_key,
                symbol=decision.symbol,
                direction=decision.direction,
                size=size,
                exchange_mode=ChallengeExchangeMode.DEMO,
            )
            receipt = executor.execute(intent)
            final_receipt = receipt
            if receipt.status.value in {"filled", "protected"}:
                reconciliation = executor.reconcile(intent)
                if (
                    reconciliation.protection_confirmed
                    or reconciliation.status != receipt.status
                ):
                    final_receipt = reconciliation

            execution_results.append(
                {
                    "slot_key": slot_key,
                    "symbol": intent.symbol,
                    "direction": intent.direction.value,
                    "approved": final_receipt.approved,
                    "status": final_receipt.status.value,
                    "rejection_code": final_receipt.rejection_code,
                    "exchange_order_id": final_receipt.exchange_order_id,
                    "emergency_close_order_id": final_receipt.emergency_close_order_id,
                    "attempts": final_receipt.attempts,
                    "evidence": dict(final_receipt.evidence),
                }
            )
            if final_receipt.approved and final_receipt.protection_confirmed:
                active_trades.append(
                    {
                        "slot_key": slot_key,
                        "symbol": intent.symbol,
                        "direction": intent.direction.value,
                        "quantity": str(size.quantity),
                        "entry_price": str(size.entry_price),
                        "stop_loss": str(size.stop_loss),
                        "take_profit": str(size.take_profit),
                        "estimated_fees": str(size.estimated_fees),
                        "estimated_slippage": str(size.estimated_slippage),
                        "client_order_id": intent.client_order_id,
                    }
                )
            else:
                immediate_adjustment -= size.total_estimated_loss

        runtime["active_cycle"] = {
            "cycle_number": engine.state.cycle_number,
            "plan": plan.model_dump(mode="json"),
            "selected_slots": decision_rows,
            "approved_slots": [
                {
                    "symbol": trade["symbol"],
                    "slot_key": trade["slot_key"],
                    "direction": trade["direction"],
                    "quantity": trade["quantity"],
                }
                for trade in active_trades
            ],
            "active_trades": active_trades,
            "execution_results": execution_results,
            "immediate_adjustment": str(immediate_adjustment),
        }
        runtime["last_cycle"] = {
            "planned_at": datetime.now(timezone.utc).isoformat(),
            "status": "cycle_active" if active_trades else "closed_without_active_trades",
            "selected_slots": decision_rows,
            "approved_slots": runtime["active_cycle"]["approved_slots"],
            "execution_results": execution_results,
            "finalization": None,
        }

        if not active_trades:
            final_status = engine.close_cycle(
                net_pnl=immediate_adjustment,
                reference_id=f"double-down-cycle-{engine.state.cycle_number}",
            )
            runtime["last_cycle"]["status"] = final_status.value
            runtime["last_cycle"]["finalization"] = {
                "net_pnl": str(immediate_adjustment),
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "status": final_status.value,
            }
            runtime["active_cycle"] = None
        return self._save_with_rollback(engine, previous)

    def finalize_cycle(self, challenge_id: UUID) -> dict:
        if self._bybit_service is None:
            raise RuntimeError("Challenge execution wiring is unavailable.")
        engine = self._get_engine(challenge_id)
        runtime = self._runtime.setdefault(challenge_id, self._default_runtime())
        active_cycle = runtime.get("active_cycle")
        if engine.state.status != ChallengeStatus.CYCLE_ACTIVE or not active_cycle:
            raise ValueError("challenge has no active cycle to finalize")

        previous = self._snapshot_copy(engine, challenge_id)
        total_net_pnl = Decimal(str(active_cycle.get("immediate_adjustment") or "0"))
        finalization_rows = []
        for trade in active_cycle.get("active_trades", []):
            symbol = trade["symbol"]
            direction = ChallengeDirection(trade["direction"])
            quantity = Decimal(str(trade["quantity"]))
            entry_price = Decimal(str(trade["entry_price"]))
            estimated_fees = Decimal(str(trade["estimated_fees"]))
            estimated_slippage = Decimal(str(trade["estimated_slippage"]))

            side = "Sell" if direction == ChallengeDirection.LONG else "Buy"
            self._bybit_service.emergency_close_position(
                symbol=symbol,
                side=side,
                qty=str(quantity),
                order_link_id=f"{trade['client_order_id']}-finalize"[:36],
            )
            market = self._bybit_service.get_market_snapshot(symbol).data
            close_price = Decimal(str(market.mark_price or market.last_price or entry_price))
            gross_pnl = (
                (close_price - entry_price) * quantity
                if direction == ChallengeDirection.LONG
                else (entry_price - close_price) * quantity
            )
            net_pnl = gross_pnl - estimated_fees - estimated_slippage
            total_net_pnl += net_pnl
            finalization_rows.append(
                {
                    "symbol": symbol,
                    "direction": direction.value,
                    "entry_price": str(entry_price),
                    "close_price": str(close_price),
                    "quantity": str(quantity),
                    "gross_pnl": str(gross_pnl),
                    "net_pnl": str(net_pnl),
                }
            )

        final_status = engine.close_cycle(
            net_pnl=total_net_pnl,
            reference_id=f"double-down-cycle-{engine.state.cycle_number}",
        )
        runtime["last_cycle"] = {
            **(runtime.get("last_cycle") or {}),
            "status": final_status.value,
            "finalization": {
                "net_pnl": str(total_net_pnl),
                "closed_at": datetime.now(timezone.utc).isoformat(),
                "status": final_status.value,
                "trades": finalization_rows,
            },
        }
        runtime["active_cycle"] = None
        return self._save_with_rollback(engine, previous)

    def _save(self, engine: ChallengeEngine) -> dict:
        snapshot = self._build_payload(engine)
        self._persistence.save_snapshot(engine.config.challenge_id, snapshot)
        return snapshot

    def _save_with_rollback(
        self,
        engine: ChallengeEngine,
        previous_snapshot: dict,
    ) -> dict:
        try:
            return self._save(engine)
        except Exception:
            restored = self._engine_from_snapshot(previous_snapshot)
            challenge_id = restored.config.challenge_id
            self._engines[challenge_id] = restored
            self._runtime[challenge_id] = deepcopy(previous_snapshot.get("runtime") or self._default_runtime())
            raise

    def _get_engine(self, challenge_id: UUID) -> ChallengeEngine:
        existing = self._engines.get(challenge_id)
        if existing is not None:
            self._runtime.setdefault(challenge_id, self._default_runtime())
            return existing
        snapshot = self._persistence.load_snapshot(challenge_id)
        if snapshot is None:
            raise KeyError(str(challenge_id))
        engine = self._engine_from_snapshot(snapshot)
        engine.validate_isolation()
        if engine.state.status == ChallengeStatus.CYCLE_ACTIVE and not snapshot.get("runtime", {}).get("active_cycle"):
            engine.state.status = ChallengeStatus.PAUSED
        self._engines[challenge_id] = engine
        self._runtime[challenge_id] = deepcopy(snapshot.get("runtime") or self._default_runtime())
        return engine

    def _build_payload(self, engine: ChallengeEngine) -> dict:
        challenge_id = engine.config.challenge_id
        return {
            "config": engine.config.model_dump(mode="json"),
            "state": engine.state.model_dump(mode="json"),
            "ledger": [entry.model_dump(mode="json") for entry in engine.ledger],
            "runtime": deepcopy(self._runtime.get(challenge_id) or self._default_runtime()),
        }

    def _load_market_tickers(self) -> list[ChallengeTicker]:
        payload = self._bybit_service._public_get(
            "/v5/market/tickers",
            parse.urlencode({"category": "linear"}),
        )
        tickers = []
        for row in payload.get("result", {}).get("list", []) or []:
            try:
                tickers.append(
                    ChallengeTicker(
                        symbol=str(row.get("symbol") or "").upper(),
                        price_change_pct_24h=Decimal(str((row.get("price24hPcnt") or "0"))) * Decimal("100"),
                        turnover_24h=Decimal(str(row.get("turnover24h") or "0")),
                        volume_24h=Decimal(str(row.get("volume24h") or "0")),
                        best_bid=Decimal(str(row.get("bid1Price") or "0")),
                        best_ask=Decimal(str(row.get("ask1Price") or "0")),
                        last_price=Decimal(str(row.get("lastPrice") or "0")),
                    )
                )
            except Exception:
                continue
        return tickers

    def _load_recent_candles(self, symbol: str, limit: int = 20) -> list[ClosedCandle]:
        payload = self._bybit_service._get_closed_klines(symbol, "1", limit=limit)
        rows = list(reversed(payload.get("result", {}).get("list", [])))
        candles = []
        for row in rows:
            try:
                open_time_ms = int(str(row[0]))
                open_time = datetime.fromtimestamp(open_time_ms / 1000, timezone.utc)
                candles.append(
                    ClosedCandle(
                        symbol=symbol.upper(),
                        open_time=open_time,
                        close_time=open_time + timedelta(minutes=1),
                        open=Decimal(str(row[1])),
                        high=Decimal(str(row[2])),
                        low=Decimal(str(row[3])),
                        close=Decimal(str(row[4])),
                        volume=Decimal(str(row[5])),
                    )
                )
            except Exception:
                continue
        return candles

    def _instrument_rules(self, symbol: str) -> InstrumentSizingRules:
        instrument = self._bybit_service.get_validated_symbol(symbol)["instrument"]
        lot = instrument.get("lotSizeFilter", {})
        return InstrumentSizingRules(
            min_quantity=Decimal(str(lot.get("minOrderQty") or "0.001")),
            max_quantity=Decimal(str(lot.get("maxMktOrderQty") or lot.get("maxOrderQty") or "999999")),
            quantity_step=Decimal(str(lot.get("qtyStep") or "0.001")),
            min_notional=Decimal(str(lot.get("minNotionalValue") or "5")),
        )

    def _snapshot_copy(self, engine: ChallengeEngine, challenge_id: UUID) -> dict:
        return deepcopy(
            {
                "config": engine.config.model_dump(mode="json"),
                "state": engine.state.model_dump(mode="json"),
                "ledger": [entry.model_dump(mode="json") for entry in engine.ledger],
                "runtime": deepcopy(self._runtime.get(challenge_id) or self._default_runtime()),
            }
        )

    @staticmethod
    def _engine_from_snapshot(snapshot: dict) -> ChallengeEngine:
        return ChallengeEngine(
            config=ChallengeConfig.model_validate(snapshot["config"]),
            state=ChallengeState.model_validate(snapshot["state"]),
            ledger=[
                ChallengeLedgerEntry.model_validate(row)
                for row in snapshot.get("ledger", [])
            ],
        )

    @staticmethod
    def _default_runtime() -> dict[str, Any]:
        return {
            "active_cycle": None,
            "last_cycle": None,
        }
