import unittest
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException

from app.core.enums import Direction, TradingMode
from app.services.manual_trade_service import ManualTradeService
from app.services.trade_management_service import TradeManagementService


class TradingEngineMarketSafetyTests(unittest.TestCase):
    def test_market_quality_blocks_wide_spread(self):
        service = ManualTradeService.__new__(ManualTradeService)

        with self.assertRaises(HTTPException) as context:
            service._validate_market_quality(
                symbol="BTCUSDT",
                snapshot=SimpleNamespace(spread_percent=0.50, turnover_24h=5_000_000),
            )

        self.assertIn("spread", context.exception.detail.lower())

    def test_market_quality_blocks_low_turnover(self):
        service = ManualTradeService.__new__(ManualTradeService)

        with self.assertRaises(HTTPException) as context:
            service._validate_market_quality(
                symbol="BTCUSDT",
                snapshot=SimpleNamespace(spread_percent=0.10, turnover_24h=500_000),
            )

        self.assertIn("turnover", context.exception.detail.lower())

    def test_trade_management_refreshes_live_price_from_snapshot(self):
        service = TradeManagementService.__new__(TradeManagementService)
        service._bybit_service = SimpleNamespace(
            get_market_snapshot=lambda symbol: SimpleNamespace(
                data=SimpleNamespace(mark_price=105.5, last_price=105.0, index_price=104.8)
            )
        )
        trade = SimpleNamespace(symbol="BTCUSDT", current_price=100.0)

        refreshed = service._refresh_live_trade_price(trade)

        self.assertTrue(refreshed)
        self.assertEqual(trade.current_price, 105.5)

    def test_manual_order_link_id_fallback_is_deterministic(self):
        first = ManualTradeService._order_link_id(
            symbol="BTCUSDT",
            mode=TradingMode.SCALPING,
            direction=Direction.BUY,
            timeframe=None,
            signal_id=None,
        )
        second = ManualTradeService._order_link_id(
            symbol="BTCUSDT",
            mode=TradingMode.SCALPING,
            direction=Direction.BUY,
            timeframe=None,
            signal_id=None,
        )

        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 36)

    def test_protection_confirmation_accepts_matching_position(self):
        self.assertTrue(
            ManualTradeService._position_has_expected_protection(
                position={"stopLoss": "95", "takeProfit": "110"},
                stop_loss=Decimal("95"),
                take_profit=Decimal("110"),
            )
        )

    def test_protection_confirmation_retries_then_succeeds(self):
        service = ManualTradeService.__new__(ManualTradeService)
        calls = {"attach": 0}
        positions = [
            None,
            {"stopLoss": "95", "takeProfit": "110"},
        ]
        service._bybit_service = SimpleNamespace(
            get_position=lambda symbol: positions.pop(0) if positions else {"stopLoss": "95", "takeProfit": "110"},
            _private_post=lambda path, payload: calls.__setitem__("attach", calls["attach"] + 1),
            emergency_close_position=lambda **kwargs: self.fail("emergency close should not run"),
        )
        service._log = lambda *args, **kwargs: None

        service._confirm_protection_or_emergency_close(
            symbol="BTCUSDT",
            direction=Direction.BUY,
            qty="0.01",
            stop_loss=Decimal("95"),
            take_profit=Decimal("110"),
            tick_size=Decimal("0.1"),
        )

        self.assertEqual(calls["attach"], 1)

    def test_protection_confirmation_emergency_closes_after_two_failures(self):
        service = ManualTradeService.__new__(ManualTradeService)
        emergency_calls = []
        service._bybit_service = SimpleNamespace(
            get_position=lambda symbol: None,
            _private_post=lambda path, payload: {"retCode": 0},
            emergency_close_position=lambda **kwargs: emergency_calls.append(kwargs) or {"result": {"orderId": "close-1"}},
        )
        service._log = lambda *args, **kwargs: None

        with self.assertRaises(HTTPException) as context:
            service._confirm_protection_or_emergency_close(
                symbol="BTCUSDT",
                direction=Direction.BUY,
                qty="0.01",
                stop_loss=Decimal("95"),
                take_profit=Decimal("110"),
                tick_size=Decimal("0.1"),
            )

        self.assertIn("emergency close was sent", context.exception.detail.lower())
        self.assertEqual(len(emergency_calls), 1)


if __name__ == "__main__":
    unittest.main()
