from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Iterable

from fastapi import HTTPException

from app.core.trading_clock import is_on_trading_date, trading_date, trading_now
from app.db.repository import PersistenceRepository
from app.schemas.trades import ClosedTradeRecord


DAILY_TARGET_PCT = 5.0
WEEKLY_TARGET_PCT = 30.0


def week_start_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def locked_floor_for_peak(peak_pct: float) -> float:
    """Return the agreed non-decreasing daily profit floor for a peak return."""
    if peak_pct < 7.0:
        return 0.0
    if peak_pct < 10.0:
        return 5.0
    completed_steps = int((peak_pct - 10.0) // 3.0)
    return 7.0 + (completed_steps * 3.0)


@dataclass
class ProfitTrackingState:
    trading_day: date
    week_start: date
    daily_start_equity: float | None = None
    weekly_start_equity: float | None = None
    daily_realized_pnl: float = 0.0
    daily_realized_pct: float = 0.0
    daily_peak_profit_pct: float = 0.0
    daily_locked_floor_pct: float = 0.0
    weekly_realized_pnl: float = 0.0
    weekly_realized_pct: float = 0.0
    weekly_peak_profit_pct: float = 0.0
    daily_target_pct: float = DAILY_TARGET_PCT
    weekly_target_pct: float = WEEKLY_TARGET_PCT
    updated_at: str | None = None


class ProfitTrackingService:
    def __init__(self, repository: PersistenceRepository | None = None) -> None:
        today = trading_date()
        self._repository = repository
        self._state = ProfitTrackingState(
            trading_day=today,
            week_start=week_start_for(today),
        )

    def reload_from_persistence(self) -> None:
        if self._repository is None:
            return
        payload = self._repository.load_profit_tracking_state()
        if not payload:
            return
        try:
            self._state = ProfitTrackingState(
                **{
                    **payload,
                    "trading_day": date.fromisoformat(str(payload["trading_day"])),
                    "week_start": date.fromisoformat(str(payload["week_start"])),
                }
            )
        except (KeyError, TypeError, ValueError):
            return
        self._roll_periods_if_needed()

    def snapshot(self) -> ProfitTrackingState:
        self._roll_periods_if_needed()
        return ProfitTrackingState(**asdict(self._state))

    def refresh(
        self,
        *,
        closed_trades: Iterable[ClosedTradeRecord],
        account_equity: float | None,
        unrealized_pnl: float = 0.0,
    ) -> ProfitTrackingState:
        self._roll_periods_if_needed()
        trades = list(closed_trades)
        daily_realized = self._sum_realized_for_day(trades, self._state.trading_day)
        weekly_realized = self._sum_realized_for_week(trades, self._state.week_start)

        if account_equity is not None and account_equity > 0:
            if self._state.daily_start_equity is None:
                self._state.daily_start_equity = max(
                    account_equity - daily_realized - unrealized_pnl,
                    0.01,
                )
            if self._state.weekly_start_equity is None:
                self._state.weekly_start_equity = max(
                    account_equity - weekly_realized - unrealized_pnl,
                    0.01,
                )

        self._state.daily_realized_pnl = daily_realized
        self._state.weekly_realized_pnl = weekly_realized
        self._state.daily_realized_pct = self._percentage(
            daily_realized, self._state.daily_start_equity
        )
        self._state.weekly_realized_pct = self._percentage(
            weekly_realized, self._state.weekly_start_equity
        )
        self._state.daily_peak_profit_pct = max(
            self._state.daily_peak_profit_pct,
            self._state.daily_realized_pct,
        )
        self._state.weekly_peak_profit_pct = max(
            self._state.weekly_peak_profit_pct,
            self._state.weekly_realized_pct,
        )
        self._state.daily_locked_floor_pct = max(
            self._state.daily_locked_floor_pct,
            locked_floor_for_peak(self._state.daily_peak_profit_pct),
        )
        self._state.updated_at = trading_now().isoformat()
        self._persist()
        return self.snapshot()

    def refresh_from_sources(self, trade_service, bybit_service) -> ProfitTrackingState:
        trade_service.sync_with_exchange(bybit_service)
        closed_trades = trade_service.get_closed_trades().data.closed_trades
        active_data = trade_service.get_active_trades().data
        active = [*active_data.scalping_trades, *active_data.intraday_trades]
        unrealized = sum(float(trade.pnl or 0.0) for trade in active)
        equity = None
        try:
            wallet = bybit_service.get_wallet_snapshot()
            equity = float(wallet["equity"])
        except (HTTPException, KeyError, TypeError, ValueError):
            pass
        return self.refresh(
            closed_trades=closed_trades,
            account_equity=equity,
            unrealized_pnl=unrealized,
        )

    def _roll_periods_if_needed(self) -> None:
        today = trading_date()
        current_week = week_start_for(today)
        changed = False
        if today != self._state.trading_day:
            self._state.trading_day = today
            self._state.daily_start_equity = None
            self._state.daily_realized_pnl = 0.0
            self._state.daily_realized_pct = 0.0
            self._state.daily_peak_profit_pct = 0.0
            self._state.daily_locked_floor_pct = 0.0
            changed = True
        if current_week != self._state.week_start:
            self._state.week_start = current_week
            self._state.weekly_start_equity = None
            self._state.weekly_realized_pnl = 0.0
            self._state.weekly_realized_pct = 0.0
            self._state.weekly_peak_profit_pct = 0.0
            changed = True
        if changed:
            self._state.updated_at = trading_now().isoformat()
            self._persist()

    def _persist(self) -> None:
        if self._repository is None:
            return
        self._repository.save_profit_tracking_state(asdict(self._state))

    @staticmethod
    def _percentage(pnl: float, baseline: float | None) -> float:
        if baseline is None or baseline <= 0:
            return 0.0
        return (pnl / baseline) * 100.0

    @staticmethod
    def _sum_realized_for_day(
        trades: Iterable[ClosedTradeRecord], target: date
    ) -> float:
        return sum(
            float(trade.realized_pnl or 0.0)
            for trade in trades
            if is_on_trading_date(trade.closed_time, target)
        )

    @staticmethod
    def _sum_realized_for_week(
        trades: Iterable[ClosedTradeRecord], start: date
    ) -> float:
        total = 0.0
        for trade in trades:
            for offset in range(7):
                if is_on_trading_date(trade.closed_time, start + timedelta(days=offset)):
                    total += float(trade.realized_pnl or 0.0)
                    break
        return total
