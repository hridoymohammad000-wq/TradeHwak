import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from pydantic import ValidationError

from app.double_down.domain import (
    calculate_cycle_plan,
    can_transition,
    determine_replanned_status,
    require_transition,
    validate_slot_set,
)
from app.double_down.enums import (
    ChallengeDirection,
    ChallengeSlotStatus,
    ChallengeSlotType,
    ChallengeStatus,
)
from app.double_down.schemas import (
    ChallengeConfig,
    ChallengeLedgerEntry,
    ChallengeSlot,
    ChallengeTrade,
)
from app.double_down.enums import ChallengeLedgerEntryType


class ChallengeConfigTests(unittest.TestCase):
    def valid_config(self) -> ChallengeConfig:
        return ChallengeConfig(
            challenge_id=uuid4(),
            starting_balance=Decimal("100"),
            target_balance=Decimal("200"),
            failure_floor=Decimal("20"),
            created_at=datetime.now(timezone.utc),
        )

    def test_v1_config_accepts_locked_rules(self) -> None:
        config = self.valid_config()
        self.assertEqual(config.cycle_risk_pct, Decimal("0.30"))
        self.assertEqual(config.max_active_trades, 3)
        self.assertEqual(config.rr_ratio, Decimal("1.0"))

    def test_target_must_be_exactly_double(self) -> None:
        with self.assertRaises(ValidationError):
            ChallengeConfig(
                challenge_id=uuid4(),
                starting_balance=Decimal("100"),
                target_balance=Decimal("150"),
                failure_floor=Decimal("20"),
                created_at=datetime.now(timezone.utc),
            )

    def test_failure_floor_must_be_below_start(self) -> None:
        with self.assertRaises(ValidationError):
            ChallengeConfig(
                challenge_id=uuid4(),
                starting_balance=Decimal("100"),
                target_balance=Decimal("200"),
                failure_floor=Decimal("100"),
                created_at=datetime.now(timezone.utc),
            )


class ChallengeRiskTests(unittest.TestCase):
    def test_cycle_plan_for_three_slots(self) -> None:
        plan = calculate_cycle_plan(Decimal("100"), 3)
        self.assertEqual(plan.total_cycle_risk, Decimal("30.00000000"))
        self.assertEqual(plan.per_slot_risk, Decimal("10.00000000"))

    def test_cycle_plan_recalculates_after_loss(self) -> None:
        plan = calculate_cycle_plan(Decimal("70"), 3)
        self.assertEqual(plan.total_cycle_risk, Decimal("21.00000000"))
        self.assertEqual(plan.per_slot_risk, Decimal("7.00000000"))

    def test_invalid_slot_count_rejected(self) -> None:
        with self.assertRaises(ValueError):
            calculate_cycle_plan(Decimal("100"), 0)


class ChallengeSlotTests(unittest.TestCase):
    def test_valid_three_slot_set(self) -> None:
        slots = [
            ChallengeSlot(slot_type=ChallengeSlotType.BTC_ANCHOR, selected_symbol="BTCUSDT"),
            ChallengeSlot(slot_type=ChallengeSlotType.TOP_GAINER, selected_symbol="ETHUSDT"),
            ChallengeSlot(slot_type=ChallengeSlotType.TOP_LOSER, selected_symbol="SOLUSDT"),
        ]
        validate_slot_set(slots)

    def test_duplicate_symbol_rejected(self) -> None:
        slots = [
            ChallengeSlot(slot_type=ChallengeSlotType.BTC_ANCHOR, selected_symbol="BTCUSDT"),
            ChallengeSlot(slot_type=ChallengeSlotType.TOP_GAINER, selected_symbol="BTCUSDT"),
        ]
        with self.assertRaises(ValueError):
            validate_slot_set(slots)

    def test_approved_slot_requires_complete_trade_intent(self) -> None:
        with self.assertRaises(ValidationError):
            ChallengeSlot(
                slot_type=ChallengeSlotType.TOP_GAINER,
                selected_symbol="ETHUSDT",
                status=ChallengeSlotStatus.APPROVED,
            )


class ChallengeStateMachineTests(unittest.TestCase):
    def test_expected_transition_is_allowed(self) -> None:
        self.assertTrue(can_transition(ChallengeStatus.DRAFT, ChallengeStatus.READY))
        require_transition(ChallengeStatus.CYCLE_ACTIVE, ChallengeStatus.REPLANNING)

    def test_terminal_state_cannot_transition(self) -> None:
        self.assertFalse(can_transition(ChallengeStatus.COMPLETED, ChallengeStatus.RUNNING))
        with self.assertRaises(ValueError):
            require_transition(ChallengeStatus.FAILED, ChallengeStatus.RUNNING)

    def test_replanned_status_outcomes(self) -> None:
        common = {
            "starting_balance": Decimal("100"),
            "target_balance": Decimal("200"),
            "failure_floor": Decimal("20"),
            "active_trade_count": 0,
        }
        self.assertEqual(
            determine_replanned_status(current_balance=Decimal("70"), **common),
            ChallengeStatus.RECOVERY,
        )
        self.assertEqual(
            determine_replanned_status(current_balance=Decimal("120"), **common),
            ChallengeStatus.RUNNING,
        )
        self.assertEqual(
            determine_replanned_status(current_balance=Decimal("200"), **common),
            ChallengeStatus.COMPLETED,
        )
        self.assertEqual(
            determine_replanned_status(current_balance=Decimal("20"), **common),
            ChallengeStatus.FAILED,
        )


class ChallengeAccountingTests(unittest.TestCase):
    def test_ledger_balance_math_is_enforced(self) -> None:
        entry = ChallengeLedgerEntry(
            entry_id=uuid4(),
            challenge_id=uuid4(),
            cycle_number=1,
            entry_type=ChallengeLedgerEntryType.TRADE_PNL,
            balance_before=Decimal("100"),
            amount=Decimal("30"),
            balance_after=Decimal("130"),
            created_at=datetime.now(timezone.utc),
        )
        self.assertEqual(entry.balance_after, Decimal("130"))

        with self.assertRaises(ValidationError):
            ChallengeLedgerEntry(
                entry_id=uuid4(),
                challenge_id=uuid4(),
                cycle_number=1,
                entry_type=ChallengeLedgerEntryType.TRADE_PNL,
                balance_before=Decimal("100"),
                amount=Decimal("30"),
                balance_after=Decimal("140"),
                created_at=datetime.now(timezone.utc),
            )

    def test_trade_direction_price_ordering(self) -> None:
        trade = ChallengeTrade(
            challenge_trade_id=uuid4(),
            challenge_id=uuid4(),
            cycle_number=1,
            slot_type=ChallengeSlotType.BTC_ANCHOR,
            symbol="btcusdt",
            direction=ChallengeDirection.LONG,
            entry_price=Decimal("100"),
            stop_loss=Decimal("99"),
            take_profit=Decimal("101"),
            quantity=Decimal("1"),
            planned_risk=Decimal("1"),
            opened_at=datetime.now(timezone.utc),
        )
        self.assertEqual(trade.symbol, "BTCUSDT")


if __name__ == "__main__":
    unittest.main()
