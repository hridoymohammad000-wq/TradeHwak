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

    def test_tp1_triggers_at_one_point_five_r(self):
        service = TradeManagementService.__new__(TradeManagementService)
        service._state = {}
        service._repository = None
        submitted = []
        stops = []
        service._submit_partial_close = lambda trade, qty, stage, key: submitted.append(
            (stage, qty)
        )
        service._tighten_stop = lambda trade, stop: stops.append(stop)
        service._persist = lambda: None
        trade = SimpleNamespace(
            symbol="BTCUSDT",
            opened_at="2099-07-11T00:00:00+00:00",
            direction=Direction.BUY,
            entry_price=100,
            current_price=160,
            stop_loss=60,
            qty="1",
            planned_risk_usdt=40,
        )

        outcome = service._manage_trade(trade)

        self.assertEqual(outcome, "tp1")
        self.assertEqual(submitted, [("tp1", Decimal("0.50"))])
        self.assertEqual(stops, [Decimal("100")])

    def test_tp2_triggers_at_two_r_after_tp1_with_reduced_quantity(self):
        service = TradeManagementService.__new__(TradeManagementService)
        key = "BTCUSDT:2099-07-11T00:00:00+00:00"
        service._state = {
            key: {
                "symbol": "BTCUSDT",
                "opened_at": "2099-07-11T00:00:00+00:00",
                "original_qty": "1",
                "tp1_done": True,
                "tp2_done": False,
                "last_stop": 100.0,
            }
        }
        service._repository = None
        submitted = []
        stops = []
        service._submit_partial_close = lambda trade, qty, stage, trade_key: submitted.append(
            (stage, qty)
        )
        service._tighten_stop = lambda trade, stop: stops.append(stop)
        service._persist = lambda: None
        trade = SimpleNamespace(
            symbol="BTCUSDT",
            opened_at="2099-07-11T00:00:00+00:00",
            direction=Direction.BUY,
            entry_price=100,
            current_price=180,
            stop_loss=100,
            qty="0.5",
            planned_risk_usdt=40,
        )

        outcome = service._manage_trade(trade)

        self.assertEqual(outcome, "tp2")
        self.assertEqual(submitted, [("tp2", Decimal("0.30"))])
        self.assertEqual(stops, [Decimal("160.0")])

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

    def test_original_risk_uses_original_quantity_after_partial_close(self):
        trade = SimpleNamespace(planned_risk_usdt=10, qty="1")
        risk = TradeManagementService._original_risk_distance(
            trade,
            Decimal("100"),
            Decimal("95"),
            Decimal("2"),
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
