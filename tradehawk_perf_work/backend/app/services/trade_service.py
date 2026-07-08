from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException

from app.core.enums import Direction, Timeframe, TradingMode
from app.schemas.trades import (
    ActiveTradeRecord,
    ActiveTradesData,
    ActiveTradesResponse,
    ClosedTradeRecord,
    ClosedTradesData,
    ClosedTradesResponse,
    JournalSummaries,
    JournalSummary,
    TodaySummary,
)
from app.services.runtime_store import RuntimeStore
from app.services.settings_service import SettingsService


@dataclass
class ManagedTrade:
    trade_id: str
    symbol: str
    mode: TradingMode | None
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
    risk_distance: float | None = None
    risk_pct_of_entry: float | None = None
    risk_reward: float | None = None
    order_id: str | None = None
    signal_id: str | None = None
    opened_at: str | None = None
    synced_with_exchange: bool = False


class TradeService:
    def __init__(
        self,
        settings_service: SettingsService,
        runtime_store: RuntimeStore,
    ) -> None:
        self._settings_service = settings_service
        self._runtime_store = runtime_store
        persisted_state = self._runtime_store.get_section("trades", {})
        self._active_trades = self._restore_active_trades(persisted_state.get("active_trades", []))
        self._closed_trades = self._restore_closed_trades(persisted_state.get("closed_trades", []))
        self._executed_signal_ids = set(persisted_state.get("executed_signal_ids", []))
        self._trade_day = self._restore_trade_day(persisted_state.get("trade_day"))
        self._daily_trade_count = int(persisted_state.get("daily_trade_count", 0))
        self._persist_state()

    def get_active_trades(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> ActiveTradesResponse:
        self._ensure_current_day()
        settings_state = self._settings_service.get_settings_state()
        filtered = [
            trade
            for trade in self._active_trades
            if self._timestamp_in_range(trade.opened_at, start_time, end_time)
        ]
        records = [self._to_active_record(trade) for trade in filtered]
        scalping_trades = [trade for trade in records if trade.mode == TradingMode.SCALPING]
        intraday_trades = [trade for trade in records if trade.mode == TradingMode.INTRADAY]
        unknown_trades = [trade for trade in records if trade.mode is None]

        return ActiveTradesResponse(
            message="Active trades fetched successfully.",
            data=ActiveTradesData(
                today_summary=TodaySummary(
                    total_open_trades=len(records),
                    scalping_open_trades=len(scalping_trades),
                    intraday_open_trades=len(intraday_trades),
                    unknown_open_trades=len(unknown_trades),
                    closed_trades_today=self._closed_trade_count_for_range(start_time, end_time),
                    system_mode=settings_state.system_mode,
                ),
                active_trades=records,
                scalping_trades=scalping_trades,
                intraday_trades=intraday_trades,
                unknown_trades=unknown_trades,
                range_start=self._serialize_datetime(start_time),
                range_end=self._serialize_datetime(end_time),
            ),
        )

    def get_closed_trades(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> ClosedTradesResponse:
        self._ensure_current_day()
        filtered = [
            trade
            for trade in self._closed_trades
            if self._timestamp_in_range(trade.closed_time, start_time, end_time)
        ]
        return ClosedTradesResponse(
            message="Closed trades fetched successfully.",
            data=ClosedTradesData(
                closed_trades=filtered,
                summaries=self._build_journal_summaries(filtered),
                range_start=self._serialize_datetime(start_time),
                range_end=self._serialize_datetime(end_time),
            ),
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
        risk_distance: float | None = None,
        risk_pct_of_entry: float | None = None,
        risk_reward: float | None = None,
        signal_id: str | None = None,
        order_id: str | None = None,
        qty: str | None = None,
    ) -> None:
        self._ensure_current_day()
        existing_index = self._find_active_index(symbol, mode)
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        trade_record = ManagedTrade(
            trade_id=f"trd_{uuid4().hex}",
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
            risk_distance=risk_distance,
            risk_pct_of_entry=risk_pct_of_entry,
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
            self._runtime_store.append_event(
                "trade_opened",
                f"{symbol} {direction.value.upper()} trade opened in {mode.value} mode.",
            )
        else:
            current = self._active_trades[existing_index]
            trade_record.trade_id = current.trade_id
            trade_record.signal_id = signal_id or current.signal_id
            trade_record.order_id = order_id or current.order_id
            trade_record.qty = qty or current.qty
            trade_record.notional = notional or current.notional
            trade_record.planned_risk_usdt = planned_risk_usdt or current.planned_risk_usdt
            trade_record.risk_distance = risk_distance or current.risk_distance
            trade_record.risk_pct_of_entry = risk_pct_of_entry or current.risk_pct_of_entry
            trade_record.risk_reward = risk_reward or current.risk_reward
            trade_record.opened_at = current.opened_at or now_iso
            trade_record.synced_with_exchange = current.synced_with_exchange
            self._active_trades[existing_index] = trade_record
        self._persist_state()

        if signal_id:
            self._executed_signal_ids.add(signal_id)
            self._persist_state()

    def sync_with_exchange(self, bybit_service) -> None:
        self._ensure_current_day()
        if not self._active_trades and not self._closed_trades:
            return
        try:
            positions = bybit_service.get_open_positions()
            closed_pnls = bybit_service.get_closed_pnls(limit=50)
        except HTTPException:
            return

        positions_by_symbol = {
            str(item.get("symbol") or "").upper(): item
            for item in positions
            if self._position_is_open(item)
        }
        closed_by_symbol = {
            str(item.get("symbol") or "").upper(): item
            for item in closed_pnls
        }

        remaining_active: list[ManagedTrade] = []
        for trade in self._active_trades:
            position = positions_by_symbol.get(trade.symbol)
            if position:
                trade.current_price = self._safe_float(position.get("markPrice"), trade.current_price)
                trade.entry_price = self._safe_float(position.get("avgPrice"), trade.entry_price)
                trade.pnl = self._safe_float(position.get("unrealisedPnl"), trade.pnl)
                trade.stop_loss = self._safe_float(position.get("stopLoss"), trade.stop_loss)
                trade.take_profit = self._safe_float(position.get("takeProfit"), trade.take_profit)
                trade.status = "open"
                trade.synced_with_exchange = True
                remaining_active.append(trade)
                continue

            closed_trade = closed_by_symbol.get(trade.symbol)
            if closed_trade:
                closed_record = self._to_closed_record(trade, closed_trade)
                self._closed_trades.insert(0, closed_record)
                self._runtime_store.append_event(
                    "trade_closed",
                    (
                        f"{trade.symbol} closed with {closed_record.result or 'flat'} result "
                        f"({closed_record.close_reason or closed_record.status})."
                    ),
                )
                continue

            remaining_active.append(trade)

        self._active_trades = remaining_active
        self._persist_state()

    def get_open_trade_count(self) -> int:
        self._ensure_current_day()
        return len(self._active_trades)

    def get_daily_trade_count(self) -> int:
        self._ensure_current_day()
        return self._daily_trade_count

    def get_daily_realized_pnl(self) -> float:
        self._ensure_current_day()
        total = 0.0
        for trade in self._closed_trades:
            parsed = self._parse_timestamp(trade.closed_time)
            if parsed and parsed.date() == self._trade_day:
                total += trade.realized_pnl or 0.0
        return total

    def get_daily_realized_loss(self) -> float:
        realized_pnl = self.get_daily_realized_pnl()
        return abs(realized_pnl) if realized_pnl < 0 else 0.0

    def get_remaining_daily_loss_budget(self, configured_daily_max_loss: float) -> float | None:
        if configured_daily_max_loss <= 0:
            return None
        remaining = configured_daily_max_loss - self.get_daily_realized_loss()
        return max(remaining, 0.0)

    def has_open_trade_for_symbol(self, symbol: str) -> bool:
        self._ensure_current_day()
        return any(trade.symbol == symbol for trade in self._active_trades)

    def was_signal_executed(self, signal_id: str) -> bool:
        self._ensure_current_day()
        return signal_id in self._executed_signal_ids

    def _ensure_current_day(self) -> None:
        today = date.today()
        if today == self._trade_day:
            return
        self._trade_day = today
        self._daily_trade_count = 0
        self._executed_signal_ids.clear()
        self._persist_state()

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
    ) -> str:
        timeframe_value = timeframe.value if timeframe is not None else "na"
        return (
            f"sig-{symbol.lower()}-{timeframe_value.lower()}-{direction.value}-"
            f"{datetime.now(timezone.utc).date().isoformat()}"
        )

    @staticmethod
    def _to_active_record(trade: ManagedTrade) -> ActiveTradeRecord:
        return ActiveTradeRecord(
            trade_id=trade.trade_id,
            order_id=trade.order_id,
            signal_id=trade.signal_id,
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
            risk_distance=trade.risk_distance,
            risk_pct_of_entry=trade.risk_pct_of_entry,
            risk_reward=trade.risk_reward,
            pnl=trade.pnl,
            status=trade.status,
            timeframe=trade.timeframe,
            opened_at=trade.opened_at,
        )

    @staticmethod
    def _restore_trade_day(value: str | None) -> date:
        try:
            return date.fromisoformat(value) if value else date.today()
        except ValueError:
            return date.today()

    @classmethod
    def _restore_active_trades(cls, payload: list[dict]) -> list[ManagedTrade]:
        restored: list[ManagedTrade] = []
        for item in payload:
            try:
                raw_mode = item.get("mode")
                try:
                    mode = TradingMode(raw_mode) if raw_mode else None
                except ValueError:
                    mode = None
                trade_id = str(item.get("trade_id") or cls._stable_trade_id("trd_legacy", item))
                restored.append(
                    ManagedTrade(
                        trade_id=trade_id,
                        symbol=str(item["symbol"]),
                        mode=mode,
                        direction=Direction(item["direction"]),
                        entry_price=float(item["entry_price"]),
                        current_price=float(item["current_price"]),
                        stop_loss=float(item["stop_loss"]),
                        take_profit=float(item["take_profit"]),
                        pnl=float(item.get("pnl") or 0.0),
                        timeframe=Timeframe(item["timeframe"]) if item.get("timeframe") else None,
                        status=str(item.get("status") or "open"),
                        qty=item.get("qty"),
                        notional=float(item["notional"]) if item.get("notional") is not None else None,
                        planned_risk_usdt=(
                            float(item["planned_risk_usdt"])
                            if item.get("planned_risk_usdt") is not None
                            else None
                        ),
                        risk_distance=float(item["risk_distance"]) if item.get("risk_distance") is not None else None,
                        risk_pct_of_entry=(
                            float(item["risk_pct_of_entry"])
                            if item.get("risk_pct_of_entry") is not None
                            else None
                        ),
                        risk_reward=float(item["risk_reward"]) if item.get("risk_reward") is not None else None,
                        order_id=item.get("order_id"),
                        signal_id=item.get("signal_id"),
                        opened_at=item.get("opened_at"),
                        synced_with_exchange=bool(item.get("synced_with_exchange", False)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return restored

    @classmethod
    def _restore_closed_trades(cls, payload: list[dict]) -> list[ClosedTradeRecord]:
        restored: list[ClosedTradeRecord] = []
        for item in payload:
            try:
                normalized = dict(item)
                raw_mode = normalized.get("mode")
                if raw_mode not in {TradingMode.SCALPING.value, TradingMode.INTRADAY.value}:
                    normalized["mode"] = None
                normalized["trade_id"] = str(
                    normalized.get("trade_id") or cls._stable_trade_id("jr_legacy", normalized)
                )
                restored.append(ClosedTradeRecord.model_validate(normalized))
            except Exception:
                continue
        return restored

    def _persist_state(self) -> None:
        self._runtime_store.replace_section(
            "trades",
            {
                "trade_day": self._trade_day.isoformat(),
                "daily_trade_count": self._daily_trade_count,
                "executed_signal_ids": sorted(self._executed_signal_ids),
                "active_trades": [self._managed_trade_to_dict(trade) for trade in self._active_trades],
                "closed_trades": [trade.model_dump(mode="json") for trade in self._closed_trades],
            },
        )

    @staticmethod
    def _managed_trade_to_dict(trade: ManagedTrade) -> dict:
        return {
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "mode": trade.mode.value if trade.mode else None,
            "direction": trade.direction.value,
            "qty": trade.qty,
            "entry_price": trade.entry_price,
            "current_price": trade.current_price,
            "stop_loss": trade.stop_loss,
            "take_profit": trade.take_profit,
            "notional": trade.notional,
            "planned_risk_usdt": trade.planned_risk_usdt,
            "risk_distance": trade.risk_distance,
            "risk_pct_of_entry": trade.risk_pct_of_entry,
            "risk_reward": trade.risk_reward,
            "pnl": trade.pnl,
            "status": trade.status,
            "timeframe": trade.timeframe.value if trade.timeframe else None,
            "order_id": trade.order_id,
            "signal_id": trade.signal_id,
            "opened_at": trade.opened_at,
            "synced_with_exchange": trade.synced_with_exchange,
        }

    def _closed_trade_count_for_range(
        self,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> int:
        if start_time is None and end_time is None:
            return sum(
                1
                for trade in self._closed_trades
                if (parsed := self._parse_timestamp(trade.closed_time))
                and parsed.date() == self._trade_day
            )
        return sum(
            1
            for trade in self._closed_trades
            if self._timestamp_in_range(trade.closed_time, start_time, end_time)
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

    def _to_closed_record(self, trade: ManagedTrade, closed_trade: dict) -> ClosedTradeRecord:
        pnl = self._safe_float(closed_trade.get("closedPnl"), 0.0)
        exit_price = self._safe_float(
            closed_trade.get("avgExitPrice") or closed_trade.get("fillPrice"),
            trade.current_price,
        )
        updated_time = self._to_time_string(
            closed_trade.get("updatedTime") or closed_trade.get("createdTime")
        )
        close_reason, exit_analysis = self._resolve_close_analysis(trade, exit_price, pnl)
        pnl_multiple_of_risk = (
            round(pnl / trade.planned_risk_usdt, 2)
            if trade.planned_risk_usdt not in (None, 0)
            else None
        )
        stop_slippage_usdt = round(exit_price - trade.stop_loss, 4) if pnl < 0 else None
        return ClosedTradeRecord(
            trade_id=trade.trade_id,
            order_id=trade.order_id,
            signal_id=trade.signal_id,
            symbol=trade.symbol,
            mode=trade.mode,
            direction=trade.direction,
            qty=trade.qty,
            entry_price=trade.entry_price,
            exit_price=exit_price,
            stop_loss=trade.stop_loss,
            take_profit=trade.take_profit,
            notional=trade.notional,
            planned_risk_usdt=trade.planned_risk_usdt,
            risk_distance=trade.risk_distance,
            risk_pct_of_entry=trade.risk_pct_of_entry,
            realized_pnl=pnl,
            pnl_multiple_of_risk=pnl_multiple_of_risk,
            stop_slippage_usdt=stop_slippage_usdt,
            risk_reward=trade.risk_reward,
            result="win" if pnl > 0 else "loss" if pnl < 0 else "breakeven",
            status="closed_on_exchange",
            close_reason=close_reason,
            exit_analysis=exit_analysis,
            operator_summary=self._build_operator_summary(
                close_reason=close_reason,
                pnl=pnl,
                planned_risk_usdt=trade.planned_risk_usdt,
                stop_slippage_usdt=stop_slippage_usdt,
                pnl_multiple_of_risk=pnl_multiple_of_risk,
            ),
            timeframe=trade.timeframe,
            opened_at=trade.opened_at,
            closed_time=updated_time,
        )

    @classmethod
    def _build_journal_summaries(cls, trades: list[ClosedTradeRecord]) -> JournalSummaries:
        scalping = [trade for trade in trades if trade.mode == TradingMode.SCALPING]
        intraday = [trade for trade in trades if trade.mode == TradingMode.INTRADAY]
        unknown = [trade for trade in trades if trade.mode is None]
        return JournalSummaries(
            scalping=cls._summarize_trades(scalping),
            intraday=cls._summarize_trades(intraday),
            unknown=cls._summarize_trades(unknown),
            combined=cls._summarize_trades(trades),
        )

    @staticmethod
    def _summarize_trades(trades: list[ClosedTradeRecord]) -> JournalSummary:
        wins = sum(1 for trade in trades if (trade.result or "").lower() == "win")
        losses = sum(1 for trade in trades if (trade.result or "").lower() == "loss")
        classified = wins + losses
        win_rate = round((wins / classified) * 100, 2) if classified > 0 else None
        realized_pnl = (
            round(sum(float(trade.realized_pnl) for trade in trades), 8)
            if trades and all(trade.realized_pnl is not None for trade in trades)
            else None
        )
        average_risk_reward = (
            round(sum(float(trade.risk_reward) for trade in trades) / len(trades), 4)
            if trades and all(trade.risk_reward is not None for trade in trades)
            else None
        )
        return JournalSummary(
            total_trades=len(trades),
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            realized_pnl=realized_pnl,
            average_risk_reward=average_risk_reward,
        )

    @staticmethod
    def _build_operator_summary(
        *,
        close_reason: str,
        pnl: float,
        planned_risk_usdt: float | None,
        stop_slippage_usdt: float | None,
        pnl_multiple_of_risk: float | None,
    ) -> str:
        reason_label = close_reason.replace("_", " ").upper()
        risk_text = (
            f"{planned_risk_usdt:.2f} USDT planned risk"
            if planned_risk_usdt not in (None, 0)
            else "planned risk unavailable"
        )
        pnl_text = f"{pnl:.2f} USDT realized"
        multiple_text = f"{pnl_multiple_of_risk:.2f}R" if pnl_multiple_of_risk is not None else "R unavailable"
        slip_text = f", stop delta {stop_slippage_usdt:.4f}" if stop_slippage_usdt is not None else ""
        return f"{reason_label} | {pnl_text} | {multiple_text} | {risk_text}{slip_text}"

    @staticmethod
    def _to_time_string(value) -> str | None:
        try:
            timestamp = int(str(value))
        except (TypeError, ValueError):
            return None
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")

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

        if sl_gap <= tolerance:
            return "stop_loss_hit", "Exit price closed near the configured stop loss."
        if tp_gap <= tolerance:
            return "take_profit_hit", "Exit price closed near the configured take profit."
        if pnl < 0:
            return "loss_exit", "Trade closed in loss away from exact SL, likely slippage or manual/exchange close."
        if pnl > 0:
            return "profit_exit", "Trade closed in profit away from exact TP, likely manual close or trailing behavior."
        if entry_gap <= tolerance:
            return "flat_exit", "Trade closed near entry price."
        return "unknown_exit", "Close reason could not be classified from synced exchange data."

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        candidate = value.strip().replace(" ", "T")
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _timestamp_in_range(
        cls,
        value: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> bool:
        if start_time is None and end_time is None:
            return True
        parsed = cls._parse_timestamp(value)
        if parsed is None:
            return False
        start = cls._normalize_datetime(start_time)
        end = cls._normalize_datetime(end_time)
        if start is not None and parsed < start:
            return False
        if end is not None and parsed >= end:
            return False
        return True

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _serialize_datetime(cls, value: datetime | None) -> str | None:
        normalized = cls._normalize_datetime(value)
        return normalized.isoformat().replace("+00:00", "Z") if normalized else None

    @staticmethod
    def _stable_trade_id(prefix: str, payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
        return f"{prefix}_{digest}"
