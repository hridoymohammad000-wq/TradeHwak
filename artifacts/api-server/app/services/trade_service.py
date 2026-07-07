from dataclasses import asdict, dataclass
from datetime import date, datetime

from fastapi import HTTPException

from app.core.enums import Direction, Timeframe, TradingMode
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
from app.db.repository import PersistenceRepository


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
        self._trade_day = date.today()
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
                            "timeframe": Timeframe(payload["timeframe"]) if payload.get("timeframe") else None,
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
        self._executed_signal_ids = self._repository.load_executed_signal_ids(self._trade_day)
        self._daily_trade_count = sum(
            1 for trade in self._active_trades if (trade.opened_at or "").startswith(self._trade_day.isoformat())
        ) + sum(
            1 for trade in self._closed_trades if (trade.closed_time or "").startswith(self._trade_day.isoformat())
        )

    @staticmethod
    def _trade_key(trade: ManagedTrade) -> str:
        return trade.order_id or trade.signal_id or f"{trade.symbol}:{trade.mode.value}:{trade.opened_at or 'unknown'}"

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

        return ActiveTradesResponse(
            message="Active trades fetched successfully.",
            data=ActiveTradesData(
                today_summary=TodaySummary(
                    total_open_trades=len(self._active_trades),
                    scalping_open_trades=len(scalping_trades),
                    intraday_open_trades=len(intraday_trades),
                    closed_trades_today=len(self._closed_trades),
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
        now_iso = datetime.utcnow().isoformat()
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
            trade_record.planned_risk_usdt = planned_risk_usdt or current.planned_risk_usdt
            trade_record.risk_reward = risk_reward or current.risk_reward
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
                if self._repository is not None:
                    trade_key = self._trade_key(trade)
                    closed_payload = closed_record.model_dump(mode="json")
                    self._repository.upsert_trade(trade_key, "closed", closed_payload)
                    self._repository.save_journal_entry(trade_key, closed_payload)
                continue

            self._persist_active_trade(trade)
            remaining_active.append(trade)

        self._active_trades = remaining_active

    def get_open_trade_count(self) -> int:
        self._ensure_current_day()
        return len(self._active_trades)

    def get_daily_trade_count(self) -> int:
        self._ensure_current_day()
        return self._daily_trade_count

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
        self._executed_signal_ids = (
            self._repository.load_executed_signal_ids(today)
            if self._repository is not None
            else set()
        )
        self._active_trades.clear()
        self._closed_trades.clear()

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
            f"{datetime.utcnow().date().isoformat()}"
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
            closed_time=updated_time,
        )

    @staticmethod
    def _to_time_string(value) -> str | None:
        try:
            timestamp = int(str(value))
        except (TypeError, ValueError):
            return None
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")

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
