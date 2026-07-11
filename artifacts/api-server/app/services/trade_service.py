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
            except (KeyError, TypeError, ValueError):
                continue
        self._closed_trades = []
        for payload in closed_rows:
            try:
                self._closed_trades.append(ClosedTradeRecord.model_validate(payload))
            except ValueError:
                continue
        self._executed_signal_ids = self._repository.load_executed_signal_ids(
            self._trade_day
        )
        self._recalculate_daily_trade_count()

    @staticmethod
    def _trade_key(trade: ManagedTrade) -> str:
        return (
            trade.order_id
            or trade.signal_id
            or f"{trade.symbol}:{trade.mode.value}:{trade.opened_at or 'unknown'}"
        )

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
        tracked_symbols: set[str] = set()
        for trade in self._active_trades:
            position = positions_by_symbol.get(trade.symbol)
            if position:
                self._apply_position_snapshot(trade, position)
                remaining_active.append(trade)
                tracked_symbols.add(trade.symbol)
                self._persist_active_trade(trade)
                continue

            closed_trade = closed_by_symbol.get(trade.symbol)
            if closed_trade:
                closed_record = self._to_closed_record(trade, closed_trade)
                if not self._closed_record_exists(closed_record):
                    self._closed_trades.insert(0, closed_record)
                if self._repository is not None:
                    trade_key = self._trade_key(trade)
                    closed_payload = closed_record.model_dump(mode="json")
                    self._repository.upsert_trade(trade_key, "closed", closed_payload)
                    self._repository.save_journal_entry(trade_key, closed_payload)
                continue

            self._persist_active_trade(trade)
            remaining_active.append(trade)

        selected_mode = self._settings_service.get_settings_state().active_strategy_mode
        for symbol, position in positions_by_symbol.items():
            if symbol in tracked_symbols:
                continue
            imported = self._from_exchange_position(position, selected_mode)
            remaining_active.append(imported)
            self._persist_active_trade(imported)

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
    ) -> str:
        timeframe_value = timeframe.value if timeframe is not None else "na"
        return (
            f"sig-{symbol.lower()}-{timeframe_value.lower()}-{direction.value}-"
            f"{trading_date().isoformat()}"
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
        trade.synced_with_exchange = True

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
        order_id = str(position.get("positionIdx") or "")
        synthetic_key = f"exchange:{symbol}:{opened_at or 'open'}:{order_id}"
        return ManagedTrade(
            symbol=symbol,
            mode=selected_mode,
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
            order_id=synthetic_key,
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
            record.symbol == candidate.symbol
            and record.closed_time == candidate.closed_time
            and record.realized_pnl == candidate.realized_pnl
            for record in self._closed_trades
        )

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
