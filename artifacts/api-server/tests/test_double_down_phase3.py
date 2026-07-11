import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.double_down.engine import ChallengeEngine
from app.double_down.enums import ChallengeStatus


class DoubleDownPhase3EngineTests(unittest.TestCase):
    def create_engine(self) -> ChallengeEngine:
        return ChallengeEngine.create(
            starting_balance=Decimal("100"),
            failure_floor=Decimal("20"),
            challenge_id=uuid4(),
            created_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
        )

    def test_creation_is_isolated_and_deposit_is_ledgered(self):
        engine = self.create_engine()
        self.assertEqual(engine.state.status, ChallengeStatus.DRAFT)
        self.assertEqual(engine.state.current_balance, Decimal("100"))
        self.assertEqual(engine.ledger_balance(), Decimal("100"))
        self.assertEqual(len(engine.ledger), 1)
        engine.validate_isolation()

    def test_ready_start_and_cycle_plan(self):
        engine = self.create_engine()
        engine.mark_ready()
        engine.start()
        plan = engine.plan_cycle(3)
        self.assertEqual(plan.total_cycle_risk, Decimal("30.00000000"))
        self.assertEqual(plan.per_slot_risk, Decimal("10.00000000"))

    def test_loss_enters_recovery_and_replans_from_new_balance(self):
        engine = self.create_engine()
        engine.mark_ready()
        engine.start()
        engine.activate_cycle(3)
        status = engine.close_cycle(
            net_pnl=Decimal("-30"),
            fees=Decimal("0"),
            reference_id="cycle-1",
        )
        self.assertEqual(status, ChallengeStatus.RECOVERY)
        self.assertEqual(engine.state.current_balance, Decimal("70"))
        self.assertEqual(engine.ledger_balance(), Decimal("70"))
        plan = engine.plan_cycle(3)
        self.assertEqual(plan.total_cycle_risk, Decimal("21.00000000"))
        self.assertEqual(plan.per_slot_risk, Decimal("7.00000000"))

    def test_fees_are_deducted_from_cycle_result(self):
        engine = self.create_engine()
        engine.mark_ready()
        engine.start()
        engine.activate_cycle(2)
        engine.close_cycle(net_pnl=Decimal("20"), fees=Decimal("2"))
        self.assertEqual(engine.state.current_balance, Decimal("118"))
        self.assertEqual(engine.ledger[-1].amount, Decimal("18"))

    def test_target_completion_requires_closed_cycle(self):
        engine = self.create_engine()
        engine.mark_ready()
        engine.start()
        engine.activate_cycle(3)
        status = engine.close_cycle(net_pnl=Decimal("100"))
        self.assertEqual(status, ChallengeStatus.COMPLETED)
        self.assertEqual(engine.state.active_trade_count, 0)
        self.assertIsNotNone(engine.state.completed_at)

    def test_failure_floor_marks_failed(self):
        engine = self.create_engine()
        engine.mark_ready()
        engine.start()
        engine.activate_cycle(3)
        status = engine.close_cycle(net_pnl=Decimal("-80"))
        self.assertEqual(status, ChallengeStatus.FAILED)
        self.assertIsNotNone(engine.state.failed_at)

    def test_new_cycle_is_blocked_while_active(self):
        engine = self.create_engine()
        engine.mark_ready()
        engine.start()
        engine.activate_cycle(1)
        with self.assertRaises(ValueError):
            engine.plan_cycle(1)

    def test_pause_and_resume_restore_recovery_mode(self):
        engine = self.create_engine()
        engine.mark_ready()
        engine.start()
        engine.activate_cycle(1)
        engine.close_cycle(net_pnl=Decimal("-10"))
        engine.pause()
        self.assertEqual(engine.state.status, ChallengeStatus.PAUSED)
        engine.resume()
        self.assertEqual(engine.state.status, ChallengeStatus.RECOVERY)

    def test_foreign_ledger_entry_is_rejected(self):
        engine = self.create_engine()
        engine.ledger[0].challenge_id = uuid4()
        with self.assertRaises(ValueError):
            engine.validate_isolation()

    def test_snapshot_contains_only_challenge_owned_state(self):
        engine = self.create_engine()
        snapshot = engine.snapshot()
        self.assertEqual(set(snapshot.keys()), {"config", "state", "ledger"})
        self.assertNotIn("tradehawk_balance", snapshot)
        self.assertNotIn("exchange", snapshot)


if __name__ == "__main__":
    unittest.main()
