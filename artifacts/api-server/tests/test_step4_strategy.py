import unittest
from decimal import Decimal

from app.core.enums import Direction, SignalGrade, TradingMode
from app.services.manual_trade_service import ManualTradeService
from app.services.strategy_service import Candle, StrategyService


class FakeBybit:
    def get_closed_klines(self, symbol, interval, limit=80):
        rows = []
        price = Decimal("100")
        for index in range(limit):
            open_price = price + Decimal(index) * Decimal("0.05")
            close_price = open_price + Decimal("0.10")
            high = close_price + Decimal("0.20")
            low = open_price - Decimal("0.20")
            rows.append([str(index), str(open_price), str(high), str(low), str(close_price), "1000"])
        return list(reversed(rows))


class StepFourStrategyTests(unittest.TestCase):
    def test_weighted_grade_thresholds(self):
        # Canonical thresholds are locked across the current strategy and
        # trade-management contracts: A+ >= 90, A >= 85, B+ >= 75.
        self.assertEqual(StrategyService._grade_from_score(90), SignalGrade.A_PLUS)
        self.assertEqual(StrategyService._grade_from_score(89.9), SignalGrade.A)
        self.assertEqual(StrategyService._grade_from_score(85), SignalGrade.A)
        self.assertEqual(StrategyService._grade_from_score(84.9), SignalGrade.B_PLUS)
        self.assertEqual(StrategyService._grade_from_score(75), SignalGrade.B_PLUS)
        self.assertEqual(StrategyService._grade_from_score(74.9), SignalGrade.B)

    def test_atr_calculation(self):
        candles = [Candle(100 + i, 101 + i, 99 + i, 100.5 + i, 1000) for i in range(20)]
        self.assertIsNotNone(StrategyService._atr(candles, 14))

    def test_long_scalping_atr_swing_stop_and_one_point_five_rr(self):
        service = ManualTradeService.__new__(ManualTradeService)
        service._bybit_service = FakeBybit()
        service._repository = None
        stop, take = service._resolve_protection_prices(
            symbol="BTCUSDT",
            direction=Direction.BUY,
            mode=TradingMode.SCALPING,
            timeframe=None,
            market_price=Decimal("105"),
            stop_loss=None,
            take_profit=None,
        )
        self.assertLess(stop, Decimal("105"))
        self.assertGreater(take, Decimal("105"))
        self.assertAlmostEqual(float((take - Decimal("105")) / (Decimal("105") - stop)), 1.5, places=6)

    def test_short_intraday_atr_swing_stop_and_two_rr(self):
        service = ManualTradeService.__new__(ManualTradeService)
        service._bybit_service = FakeBybit()
        service._repository = None
        stop, take = service._resolve_protection_prices(
            symbol="BTCUSDT",
            direction=Direction.SELL,
            mode=TradingMode.INTRADAY,
            timeframe=None,
            market_price=Decimal("105"),
            stop_loss=None,
            take_profit=None,
        )
        self.assertGreater(stop, Decimal("105"))
        self.assertLess(take, Decimal("105"))
        self.assertAlmostEqual(float((Decimal("105") - take) / (stop - Decimal("105"))), 2.0, places=6)


if __name__ == "__main__":
    unittest.main()
