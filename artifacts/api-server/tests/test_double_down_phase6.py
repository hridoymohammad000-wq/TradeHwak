import unittest
from decimal import Decimal

from app.double_down.enums import ChallengeDirection, ChallengeSlotType
from app.double_down.risk import (
    ChallengeRiskPolicy,
    InstrumentSizingRules,
    size_challenge_position,
)
from app.double_down.strategy import StrategyDecision


class DoubleDownPhase6RiskTests(unittest.TestCase):
    def approved_decision(
        self,
        *,
        entry: str = "100",
        stop: str = "99",
        take: str = "101",
    ) -> StrategyDecision:
        return StrategyDecision(
            slot_type=ChallengeSlotType.BTC_ANCHOR,
            symbol="BTCUSDT",
            approved=True,
            direction=ChallengeDirection.LONG,
            confidence=Decimal("0.80"),
            strategy_name="test",
            entry_price=Decimal(entry),
            stop_loss=Decimal(stop),
            take_profit=Decimal(take),
            rejection_code=None,
            evidence={},
        )

    def rules(self, **overrides) -> InstrumentSizingRules:
        values = {
            "min_quantity": Decimal("0.001"),
            "max_quantity": Decimal("1000"),
            "quantity_step": Decimal("0.001"),
            "min_notional": Decimal("5"),
            "max_notional": None,
        }
        values.update(overrides)
        return InstrumentSizingRules(**values)

    def test_three_slots_use_ten_percent_each_of_starting_balance(self):
        result = size_challenge_position(
            current_balance=Decimal("100"),
            approved_slots=3,
            decision=self.approved_decision(),
            instrument=self.rules(),
        )
        self.assertTrue(result.approved)
        self.assertEqual(result.slot_risk_budget, Decimal("10.00000000"))
        self.assertLessEqual(result.total_estimated_loss, result.slot_risk_budget)

    def test_loss_replanning_uses_current_balance(self):
        result = size_challenge_position(
            current_balance=Decimal("70"),
            approved_slots=3,
            decision=self.approved_decision(),
            instrument=self.rules(),
        )
        self.assertTrue(result.approved)
        self.assertEqual(result.slot_risk_budget, Decimal("7.00000000"))
        self.assertLessEqual(result.total_estimated_loss, Decimal("7.00000000"))

    def test_quantity_is_floored_to_exchange_step(self):
        result = size_challenge_position(
            current_balance=Decimal("100"),
            approved_slots=3,
            decision=self.approved_decision(),
            instrument=self.rules(quantity_step=Decimal("0.01")),
        )
        self.assertTrue(result.approved)
        self.assertEqual(result.quantity % Decimal("0.01"), Decimal("0.00"))

    def test_fees_and_slippage_are_inside_risk_budget(self):
        result = size_challenge_position(
            current_balance=Decimal("100"),
            approved_slots=1,
            decision=self.approved_decision(),
            instrument=self.rules(),
            policy=ChallengeRiskPolicy(
                taker_fee_rate_per_side=Decimal("0.001"),
                slippage_rate=Decimal("0.002"),
            ),
        )
        self.assertTrue(result.approved)
        self.assertGreater(result.estimated_fees, Decimal("0"))
        self.assertGreater(result.estimated_slippage, Decimal("0"))
        self.assertLessEqual(result.total_estimated_loss, result.slot_risk_budget)

    def test_non_one_to_one_rr_is_rejected(self):
        result = size_challenge_position(
            current_balance=Decimal("100"),
            approved_slots=3,
            decision=self.approved_decision(take="102"),
            instrument=self.rules(),
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_code, "RR_NOT_ONE_TO_ONE")

    def test_unapproved_strategy_is_rejected(self):
        decision = self.approved_decision()
        decision = StrategyDecision(
            **{
                **decision.__dict__,
                "approved": False,
                "direction": None,
                "entry_price": None,
                "stop_loss": None,
                "take_profit": None,
                "rejection_code": "NO_DIRECTIONAL_BREAKOUT",
            }
        )
        result = size_challenge_position(
            current_balance=Decimal("100"),
            approved_slots=3,
            decision=decision,
            instrument=self.rules(),
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_code, "STRATEGY_NOT_APPROVED")

    def test_minimum_quantity_failure_is_fail_closed(self):
        result = size_challenge_position(
            current_balance=Decimal("10"),
            approved_slots=3,
            decision=self.approved_decision(entry="50000", stop="49000", take="51000"),
            instrument=self.rules(
                min_quantity=Decimal("1"),
                quantity_step=Decimal("1"),
            ),
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_code, "BELOW_MIN_QUANTITY")

    def test_minimum_notional_failure_is_fail_closed(self):
        result = size_challenge_position(
            current_balance=Decimal("1"),
            approved_slots=3,
            decision=self.approved_decision(entry="1", stop="0.99", take="1.01"),
            instrument=self.rules(min_notional=Decimal("1000")),
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_code, "BELOW_MIN_NOTIONAL")

    def test_notional_cap_limits_quantity(self):
        result = size_challenge_position(
            current_balance=Decimal("100"),
            approved_slots=1,
            decision=self.approved_decision(entry="10", stop="9.99", take="10.01"),
            instrument=self.rules(),
            policy=ChallengeRiskPolicy(max_notional_to_balance=Decimal("2")),
        )
        self.assertTrue(result.approved)
        self.assertLessEqual(result.notional, Decimal("200"))

    def test_cycle_risk_cannot_exceed_locked_thirty_percent(self):
        with self.assertRaises(ValueError):
            size_challenge_position(
                current_balance=Decimal("100"),
                approved_slots=3,
                decision=self.approved_decision(),
                instrument=self.rules(),
                policy=ChallengeRiskPolicy(cycle_risk_pct=Decimal("0.31")),
            )


if __name__ == "__main__":
    unittest.main()
