from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN

from fastapi import HTTPException

from app.core.enums import Direction, TradingMode
from app.core.trading_rules import trading_rule
from app.db.repository import PersistenceRepository
from app.services.bybit_service import BybitService
from app.services.trade_service import TradeService

logger = logging.getLogger(__name__)


class TradeManagementService:
    """Manage mode-specific exits while stops never loosen."""

    def __init__(
        self,
        bybit_service: BybitService,
        trade_service: TradeService,
        repository: PersistenceRepository | None = None,
    ) -> None:
        self._bybit_service = bybit_service
        self._trade_service = trade_service
        self._repository = repository
        self._state: dict[str, dict] = {}
        self.reload_from_persistence()

    def reload_from_persistence(self) -> None:
        if self._repository is None:
            return
        payload = self._repository.load_trade_management_state()
        if isinstance(payload, dict):
            self._state = payload

    def manage_open_trades(self) -> dict[str, int]:
        response = self._trade_service.get_active_trades().data
        trades = [*response.scalping_trades, *response.intraday_trades]
        active_keys = {self._key(trade) for trade in trades}
        self._state = {key: value for key, value in self._state.items() if key in active_keys}

        result = {
            "tp1": 0,
            "tp2": 0,
            "pending": 0,
            "refreshed": 0,
            "trailed": 0,
            "duration_closed": 0,
            "skipped": 0,
            "failed": 0,
        }
        for trade in trades:
            try:
                refreshed = self._refresh_live_trade_price(trade)
                if refreshed:
                    result["refreshed"] += 1
                outcome = self._manage_trade(trade)
                result[outcome] = result.get(outcome, 0) + 1
            except HTTPException as exc:
                result["failed"] += 1
                logger.warning("Trade management failed for %s: %s", trade.symbol, exc.detail)
            except Exception:
                result["failed"] += 1
                logger.exception("Unexpected trade management failure for %s", trade.symbol)
        self._persist()
        return result

    def _manage_trade(self, trade) -> str:
        if not self._valid_trade(trade):
            return "skipped"
        key = self._key(trade)
        state = self._state.setdefault(
            key,
            {
                "symbol": trade.symbol,
                "opened_at": trade.opened_at,
                "original_qty": str(trade.qty),
                "tp1_done": False,
                "tp2_done": False,
                "last_stop": float(trade.stop_loss),
            },
        )
        entry = Decimal(str(trade.entry_price))
        current = Decimal(str(trade.current_price))
        old_stop = Decimal(str(trade.stop_loss))
        original_qty = Decimal(str(state.get("original_qty") or trade.qty))
        risk = self._original_risk_distance(trade, entry, old_stop, original_qty)
        if risk <= 0 or original_qty <= 0:
            return "skipped"

        pending_outcome = self._resolve_pending_partial_exit(
            trade=trade,
            state=state,
            entry=entry,
            risk=risk,
        )
        if pending_outcome is not None:
            self._persist()
            return pending_outcome

        if self._duration_expired(trade):
            self._submit_partial_close(trade, Decimal(str(trade.qty)), "duration", key)
            self._persist()
            return "duration_closed"

        tp1_r, tp2_r = self._profit_targets(trade)
        r_multiple = self._r_multiple(trade.direction, entry, current, risk)

        if r_multiple >= tp1_r and not state.get("tp1_done"):
            self._queue_partial_exit(
                trade=trade,
                state=state,
                key=key,
                stage="tp1",
                requested_qty=original_qty * Decimal("0.50"),
                expected_remaining_qty=original_qty * Decimal("0.50"),
            )
            self._persist()
            return "pending"

        if r_multiple >= tp2_r and state.get("tp1_done") and not state.get("tp2_done"):
            self._queue_partial_exit(
                trade=trade,
                state=state,
                key=key,
                stage="tp2",
                requested_qty=original_qty * Decimal("0.30"),
                expected_remaining_qty=original_qty * Decimal("0.20"),
            )
            self._persist()
            return "pending"

        if (
            state.get("tp2_done")
            and r_multiple >= tp2_r
            and self._trailing_enabled(trade)
        ):
            candidate = current - risk if trade.direction == Direction.BUY else current + risk
            if self._strictly_improves(trade.direction, old_stop, candidate):
                self._tighten_stop(trade, candidate)
                state["last_stop"] = float(candidate)
                self._persist()
                return "trailed"
        return "skipped"

    def _queue_partial_exit(
        self,
        *,
        trade,
        state: dict,
        key: str,
        stage: str,
        requested_qty: Decimal,
        expected_remaining_qty: Decimal,
    ) -> None:
        order_link_id = self._order_link_id(key, stage)
        try:
            submission = self._submit_partial_close(
                trade,
                requested_qty,
                stage,
                key,
                order_link_id=order_link_id,
            )
        except TypeError:
            submission = self._submit_partial_close(
                trade,
                requested_qty,
                stage,
                key,
            )
        if isinstance(submission, tuple):
            order_id, submitted_qty = submission
        else:
            order_id = submission
            submitted_qty = min(requested_qty, Decimal(str(trade.qty)))
        state["pending_stage"] = stage
        state["pending_order_id"] = order_id
        state["pending_order_link_id"] = order_link_id
        state["pending_expected_qty"] = str(expected_remaining_qty)
        state["pending_submitted_qty"] = str(submitted_qty)
        state["pending_filled_baseline_qty"] = str(
            self._filled_qty_from_state(state, trade)
        )

    def _resolve_pending_partial_exit(
        self,
        *,
        trade,
        state: dict,
        entry: Decimal,
        risk: Decimal,
    ) -> str | None:
        stage = state.get("pending_stage")
        if stage not in {"tp1", "tp2"}:
            return None
        expected_remaining = Decimal(str(state.get("pending_expected_qty") or "0"))
        submitted_qty = Decimal(str(state.get("pending_submitted_qty") or "0"))
        current_qty = Decimal(str(trade.qty))
        order_status = self._pending_order_status(
            trade.symbol,
            state.get("pending_order_id"),
            state.get("pending_order_link_id"),
        )
        if order_status in {"Cancelled", "Rejected", "Deactivated"}:
            state.pop("pending_stage", None)
            state.pop("pending_order_id", None)
            state.pop("pending_order_link_id", None)
            state.pop("pending_expected_qty", None)
            state.pop("pending_submitted_qty", None)
            state.pop("pending_filled_baseline_qty", None)
            return "skipped"
        if order_status not in {"Filled", "PartiallyFilled"}:
            return "pending"
        filled_baseline = Decimal(str(state.get("pending_filled_baseline_qty") or "0"))
        filled_delta = max(
            Decimal("0"),
            self._filled_qty_from_state(state, trade) - filled_baseline,
        )
        if filled_delta < submitted_qty:
            return "pending"
        if current_qty > expected_remaining:
            return "pending"
        if stage == "tp1":
            self._tighten_stop(trade, entry)
            state["tp1_done"] = True
            state["last_stop"] = float(entry)
        else:
            tp1_price = (
                entry + risk * Decimal("1.5")
                if trade.direction == Direction.BUY
                else entry - risk * Decimal("1.5")
            )
            self._tighten_stop(trade, tp1_price)
            state["tp2_done"] = True
            state["last_stop"] = float(tp1_price)
        state.pop("pending_stage", None)
        state.pop("pending_order_id", None)
        state.pop("pending_order_link_id", None)
        state.pop("pending_expected_qty", None)
        state.pop("pending_submitted_qty", None)
        state.pop("pending_filled_baseline_qty", None)
        return stage

    @staticmethod
    def _profit_targets(trade) -> tuple[Decimal, Decimal]:
        mode = getattr(trade, "mode", None)
        mode_value = getattr(mode, "value", mode)
        if mode == TradingMode.INTRADAY or mode_value == TradingMode.INTRADAY.value:
            return Decimal("2"), Decimal("3")
        return Decimal("1.5"), Decimal("2")

    @staticmethod
    def _trailing_enabled(trade) -> bool:
        mode = TradeManagementService._trade_mode(trade)
        return trading_rule(mode).trailing_stop_enabled

    @staticmethod
    def _duration_expired(trade) -> bool:
        opened_at = getattr(trade, "opened_at", None)
        if not opened_at:
            return False
        try:
            opened = datetime.fromisoformat(str(opened_at).replace("Z", "+00:00"))
        except ValueError:
            return False
        if opened.tzinfo is None:
            opened = opened.replace(tzinfo=timezone.utc)
        elapsed_minutes = (
            datetime.now(timezone.utc) - opened.astimezone(timezone.utc)
        ).total_seconds() / 60
        return elapsed_minutes >= trading_rule(
            TradeManagementService._trade_mode(trade)
        ).max_trade_duration_minutes

    @staticmethod
    def _trade_mode(trade) -> TradingMode:
        mode = getattr(trade, "mode", TradingMode.SCALPING)
        if isinstance(mode, TradingMode):
            return mode
        return TradingMode(str(mode))

    def _submit_partial_close(
        self,
        trade,
        requested_qty: Decimal,
        stage: str,
        key: str,
        *,
        order_link_id: str | None = None,
    ) -> tuple[str, Decimal]:
        instrument = self._bybit_service.get_validated_symbol(trade.symbol)["instrument"]
        lot = instrument.get("lotSizeFilter", {})
        step = Decimal(str(lot.get("qtyStep") or "0"))
        min_qty = Decimal(str(lot.get("minOrderQty") or "0"))
        current_qty = Decimal(str(trade.qty))
        qty = min(requested_qty, current_qty)
        qty = self._round_down(qty, step)
        if qty <= 0 or (min_qty > 0 and qty < min_qty):
            raise HTTPException(status_code=400, detail=f"{stage} quantity is below exchange minimum.")
        side = "Sell" if trade.direction == Direction.BUY else "Buy"
        payload = {
            "category": "linear",
            "symbol": trade.symbol,
            "side": side,
            "orderType": "Market",
            "qty": self._format_decimal(qty, step),
            "timeInForce": "IOC",
            "positionIdx": 0,
            "reduceOnly": True,
            "closeOnTrigger": False,
            "orderLinkId": order_link_id or self._order_link_id(key, stage),
        }
        order = self._submit_order_with_retry(payload)
        order_id = order.get("result", {}).get("orderId")
        if not order_id:
            raise HTTPException(status_code=502, detail=f"Exchange returned no orderId for {stage}.")
        self._log(
            "partial_exit_submitted",
            {
                "symbol": trade.symbol,
                "stage": stage,
                "qty": payload["qty"],
                "order_id": order_id,
            },
        )
        return str(order_id), qty

    def _tighten_stop(self, trade, proposed: Decimal) -> None:
        instrument = self._bybit_service.get_validated_symbol(trade.symbol)["instrument"]
        tick = Decimal(str(instrument.get("priceFilter", {}).get("tickSize") or "0"))
        old_stop = Decimal(str(trade.stop_loss))
        stop = (
            self._round_down(proposed, tick)
            if trade.direction == Direction.BUY
            else self._round_up(proposed, tick)
        )
        if not self._strictly_improves(trade.direction, old_stop, stop):
            return
        payload = {
            "category": "linear",
            "symbol": trade.symbol,
            "tpslMode": "Full",
            "positionIdx": 0,
            "stopLoss": self._format_decimal(stop, tick),
            "slTriggerBy": "MarkPrice",
        }
        self._submit_stop_with_retry(payload)
        self._log(
            "stop_tightened",
            {
                "symbol": trade.symbol,
                "old_stop": float(old_stop),
                "new_stop": float(stop),
            },
        )

    def _submit_order_with_retry(self, payload: dict) -> dict:
        last_error: HTTPException | None = None
        for attempt in range(2):
            try:
                return self._bybit_service.create_private_order(payload)
            except HTTPException as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.25)
        raise last_error or HTTPException(status_code=502, detail="Order submission failed.")

    def _submit_stop_with_retry(self, payload: dict) -> None:
        last_error: HTTPException | None = None
        for attempt in range(2):
            try:
                self._bybit_service._private_post("/v5/position/trading-stop", payload)
                return
            except HTTPException as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.25)
        raise last_error or HTTPException(status_code=502, detail="Stop update failed.")

    def _pending_order_status(
        self,
        symbol: str,
        order_id: str | None,
        order_link_id: str | None,
    ) -> str | None:
        try:
            rows = self._bybit_service.get_order_history(
                symbol=symbol,
                order_id=order_id,
                order_link_id=order_link_id,
                limit=5,
            )
        except HTTPException:
            return None
        for row in rows:
            row_order_id = str(row.get("orderId") or "").strip()
            row_link_id = str(row.get("orderLinkId") or "").strip()
            if order_id and row_order_id == str(order_id):
                return str(row.get("orderStatus") or "").strip() or None
            if order_link_id and row_link_id == str(order_link_id):
                return str(row.get("orderStatus") or "").strip() or None
        return None

    @staticmethod
    def _filled_qty_from_state(state: dict, trade) -> Decimal:
        original_qty = Decimal(str(state.get("original_qty") or trade.qty or "0"))
        current_qty = Decimal(str(trade.qty or "0"))
        return original_qty - current_qty

    @staticmethod
    def _original_risk_distance(
        trade,
        entry: Decimal,
        stop: Decimal,
        original_qty: Decimal | None = None,
    ) -> Decimal:
        try:
            planned = Decimal(str(trade.planned_risk_usdt))
            qty = original_qty if original_qty is not None else Decimal(str(trade.qty))
            if planned > 0 and qty > 0:
                return planned / qty
        except (InvalidOperation, TypeError, ValueError):
            pass
        return abs(entry - stop)

    @staticmethod
    def _r_multiple(direction: Direction, entry: Decimal, current: Decimal, risk: Decimal) -> Decimal:
        reward = current - entry if direction == Direction.BUY else entry - current
        return reward / risk if risk > 0 else Decimal("0")

    @staticmethod
    def _strictly_improves(direction: Direction, old_stop: Decimal, new_stop: Decimal) -> bool:
        return new_stop > old_stop if direction == Direction.BUY else new_stop < old_stop

    @staticmethod
    def _round_down(value: Decimal, step: Decimal) -> Decimal:
        if step <= 0:
            return value
        return ((value / step).to_integral_value(rounding=ROUND_DOWN) * step).normalize()

    @staticmethod
    def _round_up(value: Decimal, step: Decimal) -> Decimal:
        if step <= 0:
            return value
        units = value / step
        rounded = units.to_integral_value(rounding=ROUND_DOWN)
        if rounded < units:
            rounded += 1
        return (rounded * step).normalize()

    @staticmethod
    def _format_decimal(value: Decimal, step: Decimal) -> str:
        normalized = step.normalize()
        decimals = abs(normalized.as_tuple().exponent) if normalized.as_tuple().exponent < 0 else 0
        return f"{value:.{decimals}f}"

    @staticmethod
    def _key(trade) -> str:
        return f"{trade.symbol}:{trade.opened_at or 'unknown'}"

    @staticmethod
    def _order_link_id(key: str, stage: str) -> str:
        compact = "".join(character for character in key if character.isalnum())[-20:]
        return f"stp4{stage}{compact}"[:36]

    @staticmethod
    def _valid_trade(trade) -> bool:
        required = (trade.entry_price, trade.current_price, trade.stop_loss, trade.qty)
        return all(value not in (None, 0, 0.0, "") for value in required)

    def _persist(self) -> None:
        if self._repository is not None:
            self._repository.save_trade_management_state(self._state)

    def _refresh_live_trade_price(self, trade) -> bool:
        snapshot_getter = getattr(self._bybit_service, "get_market_snapshot", None)
        if not callable(snapshot_getter):
            return False
        snapshot = snapshot_getter(trade.symbol).data
        candidates = [
            getattr(snapshot, "mark_price", None),
            getattr(snapshot, "last_price", None),
            getattr(snapshot, "index_price", None),
        ]
        for value in candidates:
            if value not in (None, 0, 0.0, ""):
                trade.current_price = float(value)
                return True
        return False

    def _log(self, event_type: str, payload: dict) -> None:
        if self._repository is not None:
            self._repository.append_log("execution_logs", event_type, payload)
