import unittest
from decimal import Decimal

from app.double_down.demo_execution import DemoChallengeExecutor
from app.double_down.enums import ChallengeExchangeMode
from app.double_down.risk import PositionSizeResult
from app.double_down.safety_audit import evaluate_release_safety


class DummyTransport:
    def place_market_order(self, payload):
        raise AssertionError("live/demo transport must not be called by safety tests")

    def attach_protection(self, payload):
        raise AssertionError("transport must not be called")

    def get_order(self, *, symbol, client_order_id):
        return None

    def get_position(self, *, symbol):
        return None

    def emergency_close(self, payload):
        raise AssertionError("transport must not be called")


def approved_size() -> PositionSizeResult:
    return PositionSizeResult(
        approved=True,
        rejection_code=None,
        quantity=Decimal("1"),
        entry_price=Decimal("100"),
        stop_loss=Decimal("99"),
        take_profit=Decimal("101"),
        stop_distance=Decimal("1"),
        gross_risk=Decimal("1"),
        estimated_fees=Decimal("0.1"),
        estimated_slippage=Decimal("0.1"),
        total_estimated_loss=Decimal("1.2"),
        notional=Decimal("100"),
        slot_risk_budget=Decimal("10"),
        evidence={"rr_ratio": "1.0"},
    )


class DoubleDownPhase10SafetyTests(unittest.TestCase):
    def test_exchange_enum_contains_no_live_mode(self):
        self.assertEqual({mode.value for mode in ChallengeExchangeMode}, {"paper", "demo"})

    def test_executor_constructor_hard_blocks_live_flag(self):
        with self.assertRaisesRegex(ValueError, "live trading is prohibited"):
            DemoChallengeExecutor(DummyTransport(), live_trading_enabled=True)

    def test_safety_gate_refuses_production_without_runtime_evidence(self):
        report = evaluate_release_safety(
            persistence_enabled=True,
            database_reachable=True,
            backup_verified=False,
            rollback_verified=False,
            demo_smoke_verified=False,
        )
        self.assertTrue(report.code_ready)
        self.assertFalse(report.production_ready)
        self.assertIn("BACKUP_RECOVERY_NOT_VERIFIED", report.blockers)
        self.assertIn("ROLLBACK_NOT_VERIFIED", report.blockers)
        self.assertIn("DEMO_SMOKE_NOT_VERIFIED", report.blockers)

    def test_safety_gate_requires_persistence(self):
        report = evaluate_release_safety(
            persistence_enabled=False,
            database_reachable=False,
            backup_verified=True,
            rollback_verified=True,
            demo_smoke_verified=True,
        )
        self.assertFalse(report.code_ready)
        self.assertFalse(report.production_ready)
        self.assertIn("PERSISTENCE_DISABLED", report.blockers)

    def test_production_ready_only_with_complete_evidence(self):
        report = evaluate_release_safety(
            persistence_enabled=True,
            database_reachable=True,
            backup_verified=True,
            rollback_verified=True,
            demo_smoke_verified=True,
        )
        self.assertTrue(report.code_ready)
        self.assertTrue(report.production_ready)
        self.assertEqual(report.blockers, ())

    def test_live_like_mode_cannot_be_constructed(self):
        with self.assertRaises(ValueError):
            ChallengeExchangeMode("live")


if __name__ == "__main__":
    unittest.main()
