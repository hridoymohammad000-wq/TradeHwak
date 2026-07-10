import unittest
from datetime import date
from unittest.mock import patch

from app.core.enums import Direction, TradingMode
from app.schemas.trades import ClosedTradeRecord
from app.services.profit_tracking_service import (
    ProfitTrackingService,
    locked_floor_for_peak,
)


class MemoryProfitRepository:
    def __init__(self):
        self.state = None

    def load_profit_tracking_state(self):
        return self.state

    def save_profit_tracking_state(self, state):
        self.state = state


class StepTwoProfitTrackingTests(unittest.TestCase):
    def test_dynamic_lock_ladder(self):
        self.assertEqual(locked_floor_for_peak(4.99), 0.0)
        self.assertEqual(locked_floor_for_peak(7.0), 5.0)
        self.assertEqual(locked_floor_for_peak(9.99), 5.0)
        self.assertEqual(locked_floor_for_peak(10.0), 7.0)
        self.assertEqual(locked_floor_for_peak(13.0), 10.0)
        self.assertEqual(locked_floor_for_peak(16.0), 13.0)

    def test_peak_and_lock_never_move_down_intraday(self):
        repository = MemoryProfitRepository()
        with patch("app.services.profit_tracking_service.trading_date", return_value=date(2026, 7, 11)):
            service = ProfitTrackingService(repository)
            winning = ClosedTradeRecord(
                symbol="BTCUSDT",
                mode=TradingMode.SCALPING,
                direction=Direction.BUY,
                status="closed_on_exchange",
                realized_pnl=70.0,
                closed_time="2026-07-10T18:30:00+00:00",
            )
            first = service.refresh(closed_trades=[winning], account_equity=1000.0)
            self.assertGreaterEqual(first.daily_peak_profit_pct, 7.0)
            self.assertEqual(first.daily_locked_floor_pct, 5.0)

            losing = ClosedTradeRecord(
                symbol="ETHUSDT",
                mode=TradingMode.SCALPING,
                direction=Direction.BUY,
                status="closed_on_exchange",
                realized_pnl=-30.0,
                closed_time="2026-07-10T19:00:00+00:00",
            )
            second = service.refresh(closed_trades=[winning, losing], account_equity=970.0)
            self.assertEqual(second.daily_peak_profit_pct, first.daily_peak_profit_pct)
            self.assertEqual(second.daily_locked_floor_pct, 5.0)

    def test_bdt_day_rollover_resets_daily_but_preserves_weekly(self):
        repository = MemoryProfitRepository()
        with patch("app.services.profit_tracking_service.trading_date", return_value=date(2026, 7, 11)):
            service = ProfitTrackingService(repository)
            trade = ClosedTradeRecord(
                symbol="BTCUSDT",
                mode=TradingMode.SCALPING,
                direction=Direction.BUY,
                status="closed_on_exchange",
                realized_pnl=50.0,
                closed_time="2026-07-10T18:30:00+00:00",
            )
            state = service.refresh(closed_trades=[trade], account_equity=1000.0)
            self.assertGreater(state.weekly_realized_pnl, 0)

        with patch("app.services.profit_tracking_service.trading_date", return_value=date(2026, 7, 12)):
            next_day = service.snapshot()
            self.assertEqual(next_day.daily_realized_pnl, 0.0)
            self.assertEqual(next_day.daily_peak_profit_pct, 0.0)
            self.assertEqual(next_day.daily_locked_floor_pct, 0.0)
            self.assertEqual(next_day.weekly_realized_pnl, state.weekly_realized_pnl)

    def test_restart_restores_persisted_peak_and_lock(self):
        repository = MemoryProfitRepository()
        repository.state = {
            "trading_day": "2026-07-11",
            "week_start": "2026-07-06",
            "daily_start_equity": 1000.0,
            "weekly_start_equity": 1000.0,
            "daily_realized_pnl": 100.0,
            "daily_realized_pct": 10.0,
            "daily_peak_profit_pct": 10.0,
            "daily_locked_floor_pct": 7.0,
            "weekly_realized_pnl": 100.0,
            "weekly_realized_pct": 10.0,
            "weekly_peak_profit_pct": 10.0,
            "daily_target_pct": 5.0,
            "weekly_target_pct": 30.0,
            "updated_at": "2026-07-11T12:00:00+06:00",
        }
        with patch("app.services.profit_tracking_service.trading_date", return_value=date(2026, 7, 11)):
            service = ProfitTrackingService(repository)
            service.reload_from_persistence()
            restored = service.snapshot()
        self.assertEqual(restored.daily_peak_profit_pct, 10.0)
        self.assertEqual(restored.daily_locked_floor_pct, 7.0)


if __name__ == "__main__":
    unittest.main()
