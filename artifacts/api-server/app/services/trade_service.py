from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone

from fastapi import HTTPException

from app.core.enums import Direction, Timeframe, TradingMode
from app.core.trading_clock import is_on_trading_date, trading_date, trading_now
from app.db.repository import PersistenceRepository
from app.schemas.trades import (
    ActiveTradeRecord,
    ActiveTradesData,
    ActiveTradesResponse,
    ClosedTradeRecord,
    ClosedTradesData,
    ClosedTradesResponse,
    TodaySummary,
)
from app.services.settings_service import SettingsService


@dataclass
class ManagedTrade:
    symbol: str
    mode: TradingMode
    direction: Direction
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    pnl: float
    timeframe: Timeframe | None
    status: str
    qty: str | None = None
    notional: float | None = None
    planned_risk_usdt: float | None = None
    risk_reward: float | None = None
    order_id: str | None = None
    exchange_position_id: str | None = None
    signal_id: str | None = None
    opened_at: str | None = None
    synced_with_exchange: bool = False


class TradeService:
    def __init__(
        self,
        settings_service: SettingsService,
        repository: PersistenceRepository | None = None,
    ) -> None:
        self._settings_service = settings_service
        self._repository = repository
        self._active_trades: list[ManagedTrade] = []
        self._closed_trades: list[ClosedTradeRecord] = []
        self._executed_signal_ids: set[str] = set()
        self._trade_day = trading_date()
        self._daily_trade_count = 0

    def reload_from_persistence(self) -> None:
        if self._repository is None:
            return
        active_rows, closed_rows = self._repository.load_trade_state()
        self._active_trades = []
        for payload in active_rows:
            try:
                self._active_trades.append(
                    ManagedTrade(
                        **{
                            **payload,
                            "mode": TradingMode(payload["mode"]),
                            "direction": Direction(payload["direction"]),
                            "timeframe": Timeframe(payload["timeframe"])
                            if payload.get("timeframe")
                            else None,
                        }
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(
                    "Stored active trade state is invalid; startup restore aborted."
                ) from exc
        self._closed_trades = []
        for payload in closed_rows:
            try:
                self._closed_trades.append(ClosedTradeRecord.model_validate(payload))
            except ValueError as exc:
                raise RuntimeError(
                    "Stored closed trade state is invalid; startup restore aborted."
                ) from exc
        self._executed_signal_ids = self._repository.load_executed_signal_ids(
            self._trade_day
        )
        self._recalculate_daily_trade_count()

    @staticmethod
    def _trade_key(trade: ManagedTrade) -> str:
        return (
            trade.exchange_position_id
            or trade.order_id
            or trade.signal_id
            or f"{trade.symbol}:{trade.mode.value}:{trade.opened_at or 'unknown'}"
        )

    @staticmethod
    def _trade_identity_candidates(trade: ManagedTrade) -> list[str]:
        candidates = [
            trade.exchange_position_id,
            trade.order_id
            or trade.signal_id
            or f"{trade.symbol}:{trade.mode.value}:{trade.opened_at or 'unknown'}"
        ]
        candidates.append(
            TradeService._trade_position_slot_key(
                symbol=trade.symbol,
                direction=trade.direction,
            )
        )
        if trade.order_id:
            candidates.append(trade.order_id)
        if trade.signal_id:
            candidates.append(trade.signal_id)
        return [candidate for candidate in candidates if candidate]

    def _persist_active_trade(self, trade: ManagedTrade) -> None:
        if self._repository is None:
            return
        payload = asdict(trade)
        payload["mode"] = trade.mode.value
        payload["direction"] = trade.direction.value
        payload["timeframe"] = trade.timeframe.value if trade.timeframe else None
        self._repository.upsert_trade(self._trade_key(trade), "open", payload)

    def get_active_trades(self) -> ActiveTradesResponse:
        self._ensure_current_day()
        settings_state = self._settings_service.get_settings_state()
        scalping_trades = [
            self._to_active_record(trade)
            for trade in self._active_trades
            if trade.mode == TradingMode.SCALPING
        ]
        intraday_trades = [
            self._to_active_record(trade)
            for trade in self._active_trades
            if trade.mode == TradingMode.INTRADAY
        ]
        closed_today = sum(
            1
            for trade in self._closed_trades
            if is_on_trading_date(trade.closed_time, self._trade_day)
        )

        return ActiveTradesResponse(
            message="Active trades fetched successfully.",
            data=ActiveTradesData(
                today_summary=TodaySummary(
                    total_open_trades=len(self._active_trades),
                    scalping_open_trades=len(scalping_trades),
                    intraday_open_trades=len(intraday_trades),
                    closed_trades_today=closed_today,
                    system_mode=settings_state.system_mode,
                ),
                scalping_trades=scalping_trades,
                intraday_trades=intraday_trades,
            ),
        )

    def get_closed_trades(self) -> ClosedTradesResponse:
        self._ensure_current_day()
        return ClosedTradesResponse(
            message="Closed trades fetched successfully.",
            data=ClosedTradesData(closed_trades=self._closed_trades),
        )

    def register_open_trade(
        self,
        *,
        symbol: str,
        mode: TradingMode,
        direction: Direction,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        timeframe: Timeframe | None,
        notional: float | None = None,
        planned_risk_usdt: float | None = None,
        risk_reward: float | None = None,
        signal_id: str | None = None,
        order_id: str | None = None,
        qty: str | None = None,
    ) -> None:
        self._ensure_current_day()
        existing_index = self._find_active_index(symbol, mode)
        now_iso = trading_now().astimezone(timezone.utc).isoformat()
        trade_record = ManagedTrade(
            symbol=symbol,
            mode=mode,
            direction=direction,
            qty=qty,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            notional=notional,
            planned_risk_usdt=planned_risk_usdt,
            risk_reward=risk_reward,
            pnl=0.0,
            status="open",
            timeframe=timeframe,
            order_id=order_id,
            signal_id=signal_id,
            opened_at=now_iso,
        )
        if existing_index is None:
            self._active_trades.append(trade_record)
            self._daily_trade_count += 1
        else:
            current = self._active_trades[existing_index]
            trade_record.signal_id = signal_id or current.signal_id
            trade_record.order_id = order_id or current.order_id
            trade_record.exchange_position_id = current.exchange_position_id
            trade_record.qty = qty or current.qty
            trade_record.notional = notional or current.notional
            trade_record.planned_risk_usdt = (
                planned_risk_usdt
                if planned_risk_usdt is not None
                else current.planned_risk_usdt
            )
            trade_record.risk_reward = (
                risk_reward if risk_reward is not None else current.risk_reward
            )
            trade_record.opened_at = current.opened_at or now_iso
            trade_record.synced_with_exchange = current.synced_with_exchange
            self._active_trades[existing_index] = trade_record

        self._persist_active_trade(trade_record)

        if signal_id:
            self._executed_signal_ids.add(signal_id)
            if self._repository is not None:
                self._repository.save_executed_signal_id(signal_id, self._trade_day)

    def sync_with_exchange(self, bybit_service) -> None:
        self._ensure_current_day()
        try:
            positions = bybit_service.get_open_positions()
            closed_pnls = bybit_service.get_closed_pnls(limit=100)
        except HTTPException:
            return

        open_positions = [
            item
            for item in positions
            if self._position_is_open(item)
        ]
        positions_by_key = {
            self._position_slot_key(item): item
            for item in open_positions
        }
        closed_by_symbol: dict[str, list[dict]] = defaultdict(list)
        for item in closed_pnls:
            symbol = str(item.get("symbol") or "").upper()
            if symbol:
                closed_by_symbol[symbol].append(item)
        for rows in closed_by_symbol.values():
            rows.sort(
                key=lambda row: int(str(row.get("updatedTime") or row.get("createdTime") or 0)),
                reverse=True,
            )

        selected_mode = self._settings_service.get_settings_state().active_strategy_mode
        remaining_active: list[ManagedTrade] = []
        tracked_position_keys: set[str] = set()
        consumed_closed_keys: set[str] = set()
        for trade in self._active_trades:
            symbol = trade.symbol.upper()
            match = self._find_matching_open_position(
                trade=trade,
                positions_by_key=positions_by_key,
                consumed_position_keys=tracked_position_keys,
            )
            position_key, position = match if match is not None else (None, None)
            if position:
                self._apply_position_snapshot(trade, position)
                remaining_active.append(trade)
                if position_key is not None:
                    tracked_position_keys.add(position_key)
                self._persist_active_trade(trade)
                continue

            candidates = [
                row
                for row in closed_by_symbol.get(symbol, [])
                if self._closed_trade_key(row) not in consumed_closed_keys
            ]
            closed_trade = self._select_matching_closed_trade(trade, candidates)
            if closed_trade is not None:
                consumed_closed_keys.add(self._closed_trade_key(closed_trade))
                closed_record = self._to_closed_record(trade, closed_trade)
                self._persist_closed_trade(self._trade_key(trade), closed_record)
                continue

        for position_key, position in positions_by_key.items():
            if position_key in tracked_position_keys:
                continue
            imported = self._from_exchange_position(position, selected_mode)
            remaining_active.append(imported)
            self._persist_active_trade(imported)

        for row in closed_pnls:
            key = self._closed_trade_key(row)
            if key in consumed_closed_keys:
                continue
            managed = self._managed_from_closed_row(row, selected_mode)
            closed_record = self._to_closed_record(managed, row)
            self._persist_closed_trade(key, closed_record)

        self._active_trades = remaining_active
        self._recalculate_daily_trade_count()

    def get_open_trade_count(self) -> int:
        self._ensure_current_day()
        return len(self._active_trades)

    def get_daily_trade_count(self) -> int:
        self._ensure_current_day()
        return self._daily_trade_count

    def get_daily_realized_pnl(self) -> float:
        self._ensure_current_day()
        return sum(
            float(trade.realized_pnl or 0.0)
            for trade in self._closed_trades
            if is_on_trading_date(trade.closed_time, self._trade_day)
        )

    def get_daily_realized_loss(self) -> float:
        realized_pnl = self.get_daily_realized_pnl()
        return abs(realized_pnl) if realized_pnl < 0 else 0.0

    def get_remaining_daily_loss_budget(
        self,
        configured_daily_max_loss: float,
    ) -> float:
        return max(
            float(configured_daily_max_loss) - self.get_daily_realized_loss(),
            0.0,
        )

    def has_open_trade_for_symbol(self, symbol: str) -> bool:
        self._ensure_current_day()
        normalized = symbol.upper()
        return any(trade.symbol == normalized for trade in self._active_trades)

    def was_signal_executed(self, signal_id: str) -> bool:
        self._ensure_current_day()
        return signal_id in self._executed_signal_ids

    def _ensure_current_day(self) -> None:
        today = trading_date()
        if today == self._trade_day:
            return
        self._trade_day = today
        self._executed_signal_ids = (
            self._repository.load_executed_signal_ids(today)
            if self._repository is not None
            else set()
        )
        self._recalculate_daily_trade_count()

    def _recalculate_daily_trade_count(self) -> None:
        active_count = sum(
            1
            for trade in self._active_trades
            if is_on_trading_date(trade.opened_at, self._trade_day)
        )
        closed_count = sum(
            1
            for trade in self._closed_trades
            if is_on_trading_date(trade.opened_at, self._trade_day)
        )
        self._daily_trade_count = active_count + closed_count

    def _find_active_index(self, symbol: str, mode: TradingMode) -> int | None:
        return next(
            (
                index
                for index, trade in enumerate(self._active_trades)
                if trade.symbol == symbol and trade.mode == mode
            ),
            None,
        )

    @staticmethod
    def build_signal_id(
        *,
        symbol: str,
        timeframe: Timeframe | None,
        direction: Direction,
        setup_timestamp: int | str | None = None,
    ) -> str:
        timeframe_value = timeframe.value if timeframe is not None else "na"
        setup_part = ""
        if setup_timestamp not in (None, ""):
            setup_compact = "".join(
                character
                for character in str(setup_timestamp)
                if character.isalnum()
            )[:20]
            if setup_compact:
                setup_part = f"{setup_compact}-"
        return (
            f"sig-{symbol.lower()}-{timeframe_value.lower()}-{direction.value}-"
            f"{setup_part}{trading_date().isoformat()}"
        )

    @staticmethod
    def _to_active_record(trade: ManagedTrade) -> ActiveTradeRecord:
        return ActiveTradeRecord(
            symbol=trade.symbol,
            mode=trade.mode,
            direction=trade.direction,
            qty=trade.qty,
            entry_price=trade.entry_price,
            current_price=trade.current_price,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            notional=trade.notional,
            planned_risk_usdt=trade.planned_risk_usdt,
            risk_reward=trade.risk_reward,
            pnl=trade.pnl,
            status=trade.status,
            timeframe=trade.timeframe,
            opened_at=trade.opened_at,
        )

    @staticmethod
    def _position_is_open(position: dict) -> bool:
        try:
            size = float(position.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        return size > 0

    @staticmethod
    def _safe_float(value, fallback: float) -> float:
        try:
            if value in (None, ""):
                return fallback
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _apply_position_snapshot(self, trade: ManagedTrade, position: dict) -> None:
        trade.current_price = self._safe_float(
            position.get("markPrice"), trade.current_price
        )
        trade.entry_price = self._safe_float(
            position.get("avgPrice"), trade.entry_price
        )
        trade.pnl = self._safe_float(position.get("unrealisedPnl"), trade.pnl)
        trade.stop_loss = self._safe_float(position.get("stopLoss"), trade.stop_loss)
        trade.take_profit = self._safe_float(
            position.get("takeProfit"), trade.take_profit
        )
        trade.qty = str(position.get("size") or trade.qty or "") or None
        trade.status = "open"
        trade.exchange_position_id = self._position_slot_key(position)
        trade.synced_with_exchange = True

    def _find_matching_open_position(
        self,
        *,
        trade: ManagedTrade,
        positions_by_key: dict[str, dict],
        consumed_position_keys: set[str],
    ) -> tuple[str, dict] | None:
        identity_candidates = set(self._trade_identity_candidates(trade))
        for position_key, position in positions_by_key.items():
            if position_key in consumed_position_keys:
                continue
            if identity_candidates.intersection(self._position_identity_candidates(position)):
                return position_key, position

        scored: list[tuple[int, str, dict]] = []
        for position_key, position in positions_by_key.items():
            if position_key in consumed_position_keys:
                continue
            if self._direction_from_position(position) != trade.direction:
                continue
            score = 0
            if str(position.get("symbol") or "").upper() == trade.symbol.upper():
                score += 4
            score += 4
            try:
                if trade.qty and float(position.get("size") or 0) == float(trade.qty):
                    score += 2
            except (TypeError, ValueError):
                pass
            if abs(
                self._safe_float(position.get("avgPrice"), trade.entry_price)
                - trade.entry_price
            ) <= max(abs(trade.entry_price) * 0.002, 0.0005):
                score += 2
            scored.append((score, position_key, position))

        scored.sort(key=lambda item: item[0], reverse=True)
        return (scored[0][1], scored[0][2]) if scored and scored[0][0] >= 8 else None

    def _from_exchange_position(
        self,
        position: dict,
        selected_mode: TradingMode,
    ) -> ManagedTrade:
        symbol = str(position.get("symbol") or "").upper()
        direction = (
            Direction.BUY
            if str(position.get("side") or "").lower() == "buy"
            else Direction.SELL
        )
        entry = self._safe_float(position.get("avgPrice"), 0.0)
        current = self._safe_float(position.get("markPrice"), entry)
        stop = self._safe_float(position.get("stopLoss"), 0.0)
        take = self._safe_float(position.get("takeProfit"), 0.0)
        qty = str(position.get("size") or "") or None
        qty_float = self._safe_float(position.get("size"), 0.0)
        notional = qty_float * entry if qty_float > 0 and entry > 0 else None
        planned_risk = (
            qty_float * abs(entry - stop)
            if qty_float > 0 and entry > 0 and stop > 0
            else None
        )
        risk_reward = None
        if stop > 0 and take > 0 and entry > 0:
            risk = abs(entry - stop)
            reward = abs(take - entry)
            risk_reward = reward / risk if risk > 0 else None

        opened_at = self._to_iso_time(
            position.get("createdTime") or position.get("updatedTime")
        )
        position_identity = self._position_identity(position)
        restored_mode = self._restore_trade_mode(
            symbol=symbol,
            opened_at=opened_at,
            direction=direction,
            entry_price=entry,
            default_mode=selected_mode,
        )
        return ManagedTrade(
            symbol=symbol,
            mode=restored_mode,
            direction=direction,
            entry_price=entry,
            current_price=current,
            stop_loss=stop,
            take_profit=take,
            pnl=self._safe_float(position.get("unrealisedPnl"), 0.0),
            timeframe=None,
            status="exchange_open_untracked",
            qty=qty,
            notional=notional,
            planned_risk_usdt=planned_risk,
            risk_reward=risk_reward,
            exchange_position_id=position_identity,
            order_id=str(position.get("orderId") or "").strip() or None,
            opened_at=opened_at,
            synced_with_exchange=True,
        )

    def _to_closed_record(
        self,
        trade: ManagedTrade,
        closed_trade: dict,
    ) -> ClosedTradeRecord:
        pnl = self._safe_float(closed_trade.get("closedPnl"), 0.0)
        exit_price = self._safe_float(
            closed_trade.get("avgExitPrice") or closed_trade.get("fillPrice"),
            trade.current_price,
        )
        updated_time = self._to_time_string(
            closed_trade.get("updatedTime") or closed_trade.get("createdTime")
        )
        close_reason, exit_analysis = self._resolve_close_analysis(
            trade, exit_price, pnl
        )
        return ClosedTradeRecord(
            symbol=trade.symbol,
            mode=trade.mode,
            direction=trade.direction,
            external_id=self._closed_trade_key(closed_trade),
            qty=trade.qty,
            entry_price=trade.entry_price,
            exit_price=exit_price,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            notional=trade.notional,
            planned_risk_usdt=trade.planned_risk_usdt,
            realized_pnl=pnl,
            risk_reward=trade.risk_reward,
            result="win" if pnl >= 0 else "loss",
            status="closed_on_exchange",
            close_reason=close_reason,
            exit_analysis=exit_analysis,
            timeframe=trade.timeframe,
            opened_at=trade.opened_at,
            closed_time=updated_time,
        )

    def _closed_record_exists(self, candidate: ClosedTradeRecord) -> bool:
        return any(
            (
                candidate.external_id is not None
                and record.external_id == candidate.external_id
            )
            or (
                record.symbol == candidate.symbol
                and record.closed_time == candidate.closed_time
                and record.realized_pnl == candidate.realized_pnl
            )
            for record in self._closed_trades
        )

    def _persist_closed_trade(
        self,
        trade_key: str,
        closed_record: ClosedTradeRecord,
    ) -> None:
        if not self._closed_record_exists(closed_record):
            self._closed_trades.insert(0, closed_record)
        if self._repository is None:
            return
        closed_payload = closed_record.model_dump(mode="json")
        self._repository.upsert_trade(trade_key, "closed", closed_payload)
        self._repository.save_journal_entry(trade_key, closed_payload)

    @staticmethod
    def _closed_trade_key(row: dict) -> str:
        order_id = str(row.get("orderId") or row.get("execId") or "").strip()
        symbol = str(row.get("symbol") or "UNKNOWN").upper()
        position_idx = str(row.get("positionIdx") or "0").strip()
        updated = str(row.get("updatedTime") or row.get("createdTime") or "unknown")
        pnl = str(row.get("closedPnl") or "0")
        side = str(row.get("side") or "unknown").lower()
        return f"exchange-closed:{order_id or f'{symbol}:{side}:{position_idx}:{updated}:{pnl}'}"

    def _managed_from_closed_row(
        self,
        row: dict,
        selected_mode: TradingMode,
    ) -> ManagedTrade:
        symbol = str(row.get("symbol") or "").upper()
        side = str(row.get("side") or "").lower()
        direction = Direction.SELL if side == "buy" else Direction.BUY
        entry = self._safe_float(row.get("avgEntryPrice") or row.get("entryPrice"), 0.0)
        exit_price = self._safe_float(row.get("avgExitPrice") or row.get("fillPrice"), entry)
        qty = str(row.get("qty") or row.get("closedSize") or "") or None
        qty_float = self._safe_float(qty, 0.0)
        opened_at = self._to_iso_time(row.get("createdTime"))
        restored_mode = self._restore_trade_mode(
            symbol=symbol,
            opened_at=opened_at,
            direction=direction,
            entry_price=entry,
            default_mode=selected_mode,
        )
        return ManagedTrade(
            symbol=symbol,
            mode=restored_mode,
            direction=direction,
            entry_price=entry,
            current_price=exit_price,
            stop_loss=0.0,
            take_profit=0.0,
            pnl=self._safe_float(row.get("closedPnl"), 0.0),
            timeframe=None,
            status="exchange_closed_imported",
            qty=qty,
            notional=qty_float * entry if qty_float > 0 and entry > 0 else None,
            planned_risk_usdt=None,
            risk_reward=None,
            exchange_position_id=self._closed_trade_key(row),
            order_id=self._closed_trade_key(row),
            opened_at=opened_at,
            synced_with_exchange=True,
        )

    def _select_matching_closed_trade(
        self,
        trade: ManagedTrade,
        candidates: list[dict],
    ) -> dict | None:
        if not candidates:
            return None
        identity_candidates = set(self._trade_identity_candidates(trade))
        for row in candidates:
            row_order_id = str(row.get("orderId") or row.get("execId") or "").strip()
            if row_order_id and row_order_id in identity_candidates:
                return row

        scored: list[tuple[int, int, dict]] = []
        for row in candidates:
            score = 0
            row_direction = self._direction_from_closed_row(row)
            if row_direction == trade.direction:
                score += 4
            try:
                if trade.qty and float(row.get("qty") or row.get("closedSize") or 0) == float(trade.qty):
                    score += 2
            except (TypeError, ValueError):
                pass
            if abs(
                self._safe_float(row.get("avgEntryPrice") or row.get("entryPrice"), trade.entry_price)
                - trade.entry_price
            ) <= max(abs(trade.entry_price) * 0.002, 0.0005):
                score += 2
            timestamp = int(str(row.get("updatedTime") or row.get("createdTime") or 0))
            scored.append((score, timestamp, row))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return scored[0][2] if scored and scored[0][0] > 0 else None

    def _restore_trade_mode(
        self,
        *,
        symbol: str,
        opened_at: str | None,
        direction: Direction,
        entry_price: float,
        default_mode: TradingMode,
    ) -> TradingMode:
        candidates: list[tuple[int, TradingMode]] = []
        opened_ts = self._timestamp_from_iso(opened_at)
        for trade in self._active_trades:
            if trade.symbol != symbol:
                continue
            score = 0
            if trade.direction == direction:
                score += 3
            if trade.opened_at and opened_ts is not None:
                delta = abs((self._timestamp_from_iso(trade.opened_at) or opened_ts) - opened_ts)
                if delta <= 3600:
                    score += 3
            if abs((trade.entry_price or 0.0) - entry_price) <= max(abs(entry_price) * 0.002, 0.0005):
                score += 2
            candidates.append((score, trade.mode))
        for trade in self._closed_trades:
            if trade.symbol != symbol:
                continue
            score = 0
            if trade.direction == direction:
                score += 3
            if trade.opened_at and opened_ts is not None:
                delta = abs((self._timestamp_from_iso(trade.opened_at) or opened_ts) - opened_ts)
                if delta <= 3600:
                    score += 3
            if abs((float(trade.entry_price or 0.0)) - entry_price) <= max(abs(entry_price) * 0.002, 0.0005):
                score += 2
            candidates.append((score, trade.mode))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1] if candidates and candidates[0][0] > 0 else default_mode

    @staticmethod
    def _position_identity(position: dict) -> str:
        explicit = str(
            position.get("positionId")
            or position.get("positionID")
            or position.get("id")
            or ""
        ).strip()
        if explicit:
            return f"exchange-open:{explicit}"
        return TradeService._position_slot_key(position)

    @staticmethod
    def _position_slot_key(position: dict) -> str:
        symbol = str(position.get("symbol") or "UNKNOWN").upper()
        side = str(position.get("side") or "unknown").lower()
        position_idx = str(position.get("positionIdx") or "0").strip()
        return f"exchange-open-slot:{symbol}:{side}:{position_idx}"

    @staticmethod
    def _trade_position_slot_key(
        *,
        symbol: str,
        direction: Direction,
        position_idx: str = "0",
    ) -> str:
        side = "buy" if direction == Direction.BUY else "sell"
        return f"exchange-open-slot:{str(symbol or 'UNKNOWN').upper()}:{side}:{position_idx}"

    @staticmethod
    def _position_identity_candidates(position: dict) -> set[str]:
        candidates = {
            TradeService._position_identity(position),
            TradeService._position_slot_key(position),
        }
        order_id = str(position.get("orderId") or "").strip()
        if order_id:
            candidates.add(order_id)
        return {candidate for candidate in candidates if candidate}

    @staticmethod
    def _direction_from_position(position: dict) -> Direction:
        side = str(position.get("side") or "").lower()
        return Direction.BUY if side == "buy" else Direction.SELL

    @staticmethod
    def _direction_from_closed_row(row: dict) -> Direction:
        side = str(row.get("side") or "").lower()
        return Direction.BUY if side == "sell" else Direction.SELL

    @staticmethod
    def _timestamp_from_iso(value: str | None) -> int | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())

    @staticmethod
    def _to_iso_time(value) -> str | None:
        try:
            timestamp = int(str(value))
        except (TypeError, ValueError):
            return None
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()

    @staticmethod
    def _to_time_string(value) -> str | None:
        try:
            timestamp = int(str(value))
        except (TypeError, ValueError):
            return None
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()

    @staticmethod
    def _resolve_close_analysis(
        trade: ManagedTrade,
        exit_price: float,
        pnl: float,
    ) -> tuple[str, str]:
        sl_gap = abs(exit_price - trade.stop_loss)
        tp_gap = abs(exit_price - trade.take_profit)
        entry_gap = abs(exit_price - trade.entry_price)
        reference = max(abs(trade.entry_price), 1.0)
        tolerance = max(reference * 0.0015, 0.0005)

        if trade.stop_loss > 0 and sl_gap <= tolerance:
            if pnl > 0:
                return (
                    "protected_stop_profit",
                    "Trade closed near the configured stop with positive PnL, consistent with a moved or trailing stop.",
                )
            return "stop_loss_hit", "Exit price closed near the configured stop loss."
        if trade.take_profit > 0 and tp_gap <= tolerance:
            return "take_profit_hit", "Exit price closed near the configured take profit."
        if pnl < 0:
            return (
                "loss_exit",
                "Trade closed in loss away from exact SL, likely slippage or manual/exchange close.",
            )
        if pnl > 0:
            return (
                "profit_exit",
                "Trade closed in profit away from exact TP, likely manual close or trailing behavior.",
            )
        if entry_gap <= tolerance:
            return "flat_exit", "Trade closed near entry price."
        return (
            "unknown_exit",
            "Close reason could not be classified from synced exchange data.",
        )
