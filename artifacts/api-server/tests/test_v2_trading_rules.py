import unittest
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException

from app.core.enums import Direction, Timeframe, TradingMode
from app.core.trading_rules import (
    COMBINED_DAILY_MAX_LOSS_PCT,
    COMBINED_MAX_OPEN_TRADES,
    trading_rule,
)
from app.schemas.trades import ClosedTradesData, ClosedTradesResponse
from app.services.manual_trade_service import ManualTradeService
from app.services.managed_manual_trade_service import ManagedManualTradeService
from app.services.strategy_service import StrategyService
from app.services.trade_management_service import TradeManagementService


class ClosedTradeService:
    def __init__(self, realized_pnl=0.0, combined_remaining=999.0):
        self.realized_pnl = realized_pnl
        self.combined_remaining = combined_remaining

    def get_remaining_daily_loss_budget(self, configured_daily_max_loss):
        return min(float(configured_daily_max_loss), self.combined_remaining)

    def get_closed_trades(self):
        return ClosedTradesResponse(
            message="ok",
            data=ClosedTradesData(
                closed_trades=[
                    {
                        "symbol": "BTCUSDT",
                        "mode": TradingMode.SCALPING,
                        "direction": Direction.BUY,
                        "status": "closed",
                        "realized_pnl": self.realized_pnl,
                        "closed_time": "2026-07-12T00:00:00+00:00",
                    }
                ]
            ),
        )


class V2TradingRulesTests(unittest.TestCase):
    def test_approved_mode_rules_are_centralized(self):
        scalping = trading_rule(TradingMode.SCALPING)
        intraday = trading_rule(TradingMode.INTRADAY)

        self.assertEqual(scalping.setup_timeframe, Timeframe.M1)
        self.assertEqual(scalping.risk_per_trade_pct, Decimal("0.5"))
        self.assertEqual(scalping.minimum_risk_reward, Decimal("1.5"))
        self.assertEqual(scalping.daily_max_net_loss_pct, Decimal("2"))
        self.assertEqual(scalping.max_trade_duration_minutes, 59)
        self.assertFalse(scalping.trailing_stop_enabled)

        self.assertEqual(intraday.setup_timeframe, Timeframe.M5)
        self.assertEqual(intraday.risk_per_trade_pct, Decimal("1"))
        self.assertEqual(intraday.minimum_risk_reward, Decimal("2"))
        self.assertEqual(intraday.daily_max_net_loss_pct, Decimal("3"))
        self.assertEqual(intraday.max_trade_duration_minutes, 360)
        self.assertTrue(intraday.trailing_stop_enabled)

        self.assertEqual(COMBINED_DAILY_MAX_LOSS_PCT, Decimal("5"))
        self.assertEqual(COMBINED_MAX_OPEN_TRADES, 5)

    def test_strategy_defaults_follow_approved_setup_timeframes(self):
        service = StrategyService(bybit_service=object())

        self.assertEqual(service.default_timeframe(TradingMode.SCALPING), Timeframe.M1)
        self.assertEqual(service.default_timeframe(TradingMode.INTRADAY), Timeframe.M5)

    def test_manual_daily_loss_guard_uses_mode_and_combined_percent_budgets(self):
        service = ManualTradeService.__new__(ManualTradeService)
        service._trade_service = ClosedTradeService(realized_pnl=-18.0)

        approved = service._apply_v2_daily_loss_guard(
            Decimal("5"),
            TradingMode.SCALPING,
            Decimal("1000"),
        )
        self.assertEqual(approved, Decimal("2"))

        service._trade_service = ClosedTradeService(realized_pnl=-20.0)
        with self.assertRaises(HTTPException) as context:
            service._apply_v2_daily_loss_guard(
                Decimal("5"),
                TradingMode.SCALPING,
                Decimal("1000"),
            )
        self.assertIn("Scalping daily max loss limit reached", context.exception.detail)

    def test_combined_open_limit_is_five_for_both_modes(self):
        self.assertEqual(
            ManagedManualTradeService.MODE_OPEN_LIMITS[TradingMode.SCALPING],
            5,
        )
        self.assertEqual(
            ManagedManualTradeService.MODE_OPEN_LIMITS[TradingMode.INTRADAY],
            5,
        )

    def test_scalping_does_not_trail_after_tp2(self):
        service = TradeManagementService.__new__(TradeManagementService)
        key = "BTCUSDT:2099-07-11T00:00:00+00:00"
        service._state = {
            key: {
                "symbol": "BTCUSDT",
                "opened_at": "2099-07-11T00:00:00+00:00",
                "original_qty": "1",
                "tp1_done": True,
                "tp2_done": True,
                "last_stop": 160.0,
            }
        }
        service._repository = None
        service._tighten_stop = lambda trade, stop: self.fail("scalping must not trail")
        service._persist = lambda: None
        trade = SimpleNamespace(
            symbol="BTCUSDT",
            mode=TradingMode.SCALPING,
            opened_at="2099-07-11T00:00:00+00:00",
            direction=Direction.BUY,
            entry_price=100,
            current_price=220,
            stop_loss=160,
            qty="0.2",
            planned_risk_usdt=40,
        )

        self.assertEqual(service._manage_trade(trade), "skipped")

    def test_expired_trade_is_closed_by_duration_rule(self):
        service = TradeManagementService.__new__(TradeManagementService)
        service._state = {}
        service._repository = None
        submitted = []
        service._submit_partial_close = lambda trade, qty, stage, key: submitted.append(
            (stage, qty)
        )
        service._persist = lambda: None
        trade = SimpleNamespace(
            symbol="BTCUSDT",
            mode=TradingMode.SCALPING,
            opened_at="2020-01-01T00:00:00+00:00",
            direction=Direction.BUY,
            entry_price=100,
            current_price=101,
            stop_loss=99,
            qty="1",
            planned_risk_usdt=1,
        )

        self.assertEqual(service._manage_trade(trade), "duration_closed")
        self.assertEqual(submitted, [("duration", Decimal("1"))])


if __name__ == "__main__":
    unittest.main()
