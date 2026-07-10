import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException

from app.services.manual_trade_service import ManualTradeService
from app.services.profit_tracking_service import ProfitTrackingState
from app.services.risk_execution_guard import RiskExecutionGuard


class FakeTrade:
    def __init__(self, risk):
        self.planned_risk_usdt = risk


class FakeActiveData:
    def __init__(self, risks):
        self.scalping_trades = [FakeTrade(value) for value in risks]
        self.intraday_trades = []


class FakeTradeService:
    def __init__(self, risks):
        self.risks = risks

    def get_active_trades(self):
        return type("Response", (), {"data": FakeActiveData(self.risks)})()


class FakeProfitService:
    def __init__(self, state):
        self.state = state

    def refresh_from_sources(self, trade_service, bybit_service):
        return self.state


class StepThreeRiskExecutionTests(unittest.TestCase):
    @staticmethod
    def state(realized_pct, floor_pct, baseline=1000.0):
        return ProfitTrackingState(
            trading_day=date(2026, 7, 11),
            week_start=date(2026, 7, 6),
            daily_start_equity=baseline,
            daily_realized_pct=realized_pct,
            daily_peak_profit_pct=max(realized_pct, floor_pct),
            daily_locked_floor_pct=floor_pct,
        )

    def test_no_floor_keeps_normal_configured_risk(self):
        decision = RiskExecutionGuard().evaluate(
            configured_risk_budget=25.0,
            profit_state=self.state(5.0, 0.0),
            active_planned_risk=50.0,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.approved_risk_budget, 25.0)

    def test_floor_reduces_new_risk_to_remaining_cushion(self):
        decision = RiskExecutionGuard().evaluate(
            configured_risk_budget=25.0,
            profit_state=self.state(7.0, 5.0),
            active_planned_risk=5.0,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.available_lock_cushion, 15.0)
        self.assertEqual(decision.approved_risk_budget, 15.0)

    def test_floor_blocks_when_existing_risk_consumes_cushion(self):
        decision = RiskExecutionGuard().evaluate(
            configured_risk_budget=25.0,
            profit_state=self.state(7.0, 5.0),
            active_planned_risk=20.0,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.approved_risk_budget, 0.0)
        self.assertIn("no new risk capacity", decision.reason)

    def test_higher_peak_ladder_still_uses_current_realized_cushion(self):
        decision = RiskExecutionGuard().evaluate(
            configured_risk_budget=30.0,
            profit_state=self.state(10.0, 7.0),
            active_planned_risk=10.0,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.available_lock_cushion, 20.0)
        self.assertEqual(decision.approved_risk_budget, 20.0)

    def test_manual_service_raises_before_order_when_floor_has_no_capacity(self):
        service = ManualTradeService.__new__(ManualTradeService)
        service._profit_tracking_service = FakeProfitService(self.state(7.0, 5.0))
        service._risk_execution_guard = RiskExecutionGuard()
        service._trade_service = FakeTradeService([20.0])
        service._bybit_service = object()
        service._repository = None

        with self.assertRaises(HTTPException) as context:
            service._apply_profit_lock_guard(Decimal("25"))
        self.assertIn("locked floor", str(context.exception.detail))

    def test_manual_service_returns_reduced_budget_when_capacity_remains(self):
        service = ManualTradeService.__new__(ManualTradeService)
        service._profit_tracking_service = FakeProfitService(self.state(7.0, 5.0))
        service._risk_execution_guard = RiskExecutionGuard()
        service._trade_service = FakeTradeService([5.0])
        service._bybit_service = object()
        service._repository = None

        approved = service._apply_profit_lock_guard(Decimal("25"))
        self.assertEqual(approved, Decimal("15.0"))


if __name__ == "__main__":
    unittest.main()
