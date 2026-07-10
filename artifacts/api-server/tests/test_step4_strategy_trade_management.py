import unittest
from decimal import Decimal
from types import SimpleNamespace

from app.core.enums import Direction, SignalGrade, TradingMode
from app.services.strategy_service import StrategyService
from app.services.trade_management_service import TradeManagementService


class StepFourStrategyTradeManagementTests(unittest.TestCase):
    def test_grade_thresholds_are_a_plus_90_and_a_85(self):
        self.assertEqual(StrategyService._grade_from_score(90.0), SignalGrade.A_PLUS)
        self.assertEqual(StrategyService._grade_from_score(89.99), SignalGrade.A)
        self.assertEqual(StrategyService._grade_from_score(85.0), SignalGrade.A)
        self.assertEqual(StrategyService._grade_from_score(84.99), SignalGrade.B_PLUS)

    def test_intraday_requires_ema200_alignment(self):
        self.assertTrue(StrategyService._ema200_aligned(Direction.BUY, 110.0, 100.0))
        self.assertFalse(StrategyService._ema200_aligned(Direction.BUY, 90.0, 100.0))
        self.assertTrue(StrategyService._ema200_aligned(Direction.SELL, 90.0, 100.0))
        self.assertFalse(StrategyService._ema200_aligned(Direction.SELL, 110.0, 100.0))

    def test_r_multiple_for_long_and_short(self):
        self.assertEqual(
            TradeManagementService._r_multiple(
                Direction.BUY, Decimal("100"), Decimal("102"), Decimal("1")
            ),
            Decimal("2"),
        )
        self.assertEqual(
            TradeManagementService._r_multiple(
                Direction.SELL, Decimal("100"), Decimal("97"), Decimal("1")
            ),
            Decimal("3"),
        )

    def test_stop_never_loosens(self):
        self.assertTrue(
            TradeManagementService._strictly_improves(
                Direction.BUY, Decimal("99"), Decimal("100")
            )
        )
        self.assertFalse(
            TradeManagementService._strictly_improves(
                Direction.BUY, Decimal("100"), Decimal("99")
            )
        )
        self.assertTrue(
            TradeManagementService._strictly_improves(
                Direction.SELL, Decimal("101"), Decimal("100")
            )
        )
        self.assertFalse(
            TradeManagementService._strictly_improves(
                Direction.SELL, Decimal("100"), Decimal("101")
            )
        )

    def test_original_risk_uses_planned_risk_and_quantity(self):
        trade = SimpleNamespace(planned_risk_usdt=10, qty="2")
        risk = TradeManagementService._original_risk_distance(
            trade, Decimal("100"), Decimal("95")
        )
        self.assertEqual(risk, Decimal("5"))

    def test_order_link_is_deterministic_and_within_exchange_limit(self):
        first = TradeManagementService._order_link_id(
            "BTCUSDT:2026-07-11T00:00:00+00:00", "tp1"
        )
        second = TradeManagementService._order_link_id(
            "BTCUSDT:2026-07-11T00:00:00+00:00", "tp1"
        )
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 36)

    def test_mode_scores_are_separate(self):
        scalping = StrategyService._mode_specific_score(
            TradingMode.SCALPING, Direction.BUY, 0.3, 60, 0.25, 3
        )
        intraday = StrategyService._mode_specific_score(
            TradingMode.INTRADAY, Direction.BUY, 0.3, 60, 0.25, 3
        )
        self.assertNotEqual(scalping, intraday)


if __name__ == "__main__":
    unittest.main()
