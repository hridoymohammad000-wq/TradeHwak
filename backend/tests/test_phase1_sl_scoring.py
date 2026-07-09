import unittest
from decimal import Decimal

from app.core.enums import Direction, SignalGrade, Timeframe, TradingMode
from app.services.manual_trade_service import ManualTradeService
from app.services.strategy_service import StrategyService


class FakeBybitService:
    def __init__(self, rows):
        self.rows = rows

    def get_closed_klines(self, symbol: str, interval: str, limit: int = 80):
        return list(reversed(self.rows[-limit:]))


class PhaseOneScoringTests(unittest.TestCase):
    def test_weighted_score_grades_are_not_all_hard_blockers(self):
        self.assertEqual(StrategyService._grade_from_score(86), SignalGrade.A_PLUS)
        self.assertEqual(StrategyService._grade_from_score(76), SignalGrade.A)
        self.assertEqual(StrategyService._grade_from_score(66), SignalGrade.B_PLUS)
        self.assertEqual(StrategyService._grade_from_score(60), SignalGrade.B)

    def test_volume_confirmation_is_weighted(self):
        candle_type = __import__(
            "app.services.strategy_service",
            fromlist=["Candle"],
        ).Candle
        candles = [candle_type(100, 101, 99, 100.5, 100) for _ in range(20)]
        candles.append(candle_type(100, 102, 99, 101.5, 160))
        self.assertEqual(StrategyService._volume_confirmation_score(candles), 6.0)


class PhaseOneStopLossTests(unittest.TestCase):
    @staticmethod
    def _rows():
        rows = []
        price = Decimal("100")
        for index in range(80):
            drift = Decimal(index) * Decimal("0.03")
            open_price = price + drift
            high = open_price + Decimal("0.8")
            low = open_price - Decimal("0.7")
            close = open_price + Decimal("0.2")
            rows.append([str(index), str(open_price), str(high), str(low), str(close), "1000"])
        return rows

    def _service(self):
        service = ManualTradeService.__new__(ManualTradeService)
        service._bybit_service = FakeBybitService(self._rows())
        return service

    def test_long_atr_swing_stop_is_below_entry_and_rr_is_two(self):
        service = self._service()
        entry = Decimal("102.50")
        stop, take = service._resolve_protection_prices(
            symbol="BTCUSDT",
            direction=Direction.BUY,
            mode=TradingMode.SCALPING,
            timeframe=Timeframe.M5,
            market_price=entry,
            stop_loss=None,
            take_profit=None,
        )
        self.assertLess(stop, entry)
        self.assertGreater(take, entry)
        self.assertAlmostEqual(float((take - entry) / (entry - stop)), 2.0, places=6)

    def test_short_atr_swing_stop_is_above_entry_and_rr_is_two(self):
        service = self._service()
        entry = Decimal("102.50")
        stop, take = service._resolve_protection_prices(
            symbol="BTCUSDT",
            direction=Direction.SELL,
            mode=TradingMode.INTRADAY,
            timeframe=Timeframe.M15,
            market_price=entry,
            stop_loss=None,
            take_profit=None,
        )
        self.assertGreater(stop, entry)
        self.assertLess(take, entry)
        self.assertAlmostEqual(float((entry - take) / (stop - entry)), 2.0, places=6)

    def test_atr_calculation_returns_positive_value(self):
        service = self._service()
        candles = service._load_ohlc("BTCUSDT", "5", 80)
        atr = service._atr(candles, 14)
        self.assertIsNotNone(atr)
        self.assertGreater(atr, 0)


if __name__ == "__main__":
    unittest.main()
