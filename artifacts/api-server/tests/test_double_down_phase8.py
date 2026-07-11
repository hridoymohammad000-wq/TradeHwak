import unittest
from decimal import Decimal

from app.double_down.demo_execution import (
    DemoChallengeExecutor,
    DemoExecutionIntent,
    DemoOrderStatus,
)
from app.double_down.enums import ChallengeDirection, ChallengeExchangeMode
from app.double_down.risk import PositionSizeResult


class FakeDemoTransport:
    def __init__(self):
        self.orders = {}
        self.positions = {}
        self.protection_results = []
        self.entry_calls = 0
        self.protection_calls = 0
        self.close_calls = 0

    def place_market_order(self, payload):
        self.entry_calls += 1
        order = {
            "accepted": True,
            "order_id": f"entry-{self.entry_calls}",
            "client_order_id": payload["clientOrderId"],
            "protected": False,
        }
        self.orders[payload["clientOrderId"]] = order
        self.positions[payload["symbol"]] = {
            "accepted": True,
            "order_id": order["order_id"],
            "protected": False,
        }
        return order

    def attach_protection(self, payload):
        self.protection_calls += 1
        result = self.protection_results.pop(0) if self.protection_results else {
            "accepted": True,
            "confirmed": True,
        }
        if result.get("accepted") and result.get("confirmed"):
            for order in self.orders.values():
                order["protected"] = True
            if payload["symbol"] in self.positions:
                self.positions[payload["symbol"]]["protected"] = True
        return result

    def get_order(self, *, symbol, client_order_id):
        return self.orders.get(client_order_id)

    def get_position(self, *, symbol):
        return self.positions.get(symbol)

    def emergency_close(self, payload):
        self.close_calls += 1
        self.positions.pop(payload["symbol"], None)
        return {"accepted": True, "order_id": f"close-{self.close_calls}"}


class DoubleDownPhase8Tests(unittest.TestCase):
    def size(self, approved=True):
        return PositionSizeResult(
            approved=approved,
            rejection_code=None if approved else "TEST_REJECTED",
            quantity=Decimal("0.010"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("99"),
            take_profit=Decimal("101"),
            stop_distance=Decimal("1"),
            gross_risk=Decimal("0.01"),
            estimated_fees=Decimal("0.0011"),
            estimated_slippage=Decimal("0.0005"),
            total_estimated_loss=Decimal("0.0116"),
            notional=Decimal("1"),
            slot_risk_budget=Decimal("10"),
            evidence={},
        )

    def intent(self, *, approved=True, mode=ChallengeExchangeMode.DEMO):
        return DemoExecutionIntent(
            challenge_id="12345678-1234-5678-1234-567812345678",
            cycle_number=1,
            slot_key="btc_anchor",
            symbol="BTCUSDT",
            direction=ChallengeDirection.LONG,
            size=self.size(approved=approved),
            exchange_mode=mode,
        )

    def test_live_mode_constructor_is_hard_blocked(self):
        with self.assertRaises(ValueError):
            DemoChallengeExecutor(FakeDemoTransport(), live_trading_enabled=True)

    def test_demo_order_is_filled_and_protected(self):
        transport = FakeDemoTransport()
        receipt = DemoChallengeExecutor(transport).execute(self.intent())
        self.assertTrue(receipt.approved)
        self.assertEqual(receipt.status, DemoOrderStatus.PROTECTED)
        self.assertTrue(receipt.protection_confirmed)
        self.assertEqual(transport.entry_calls, 1)
        self.assertEqual(transport.protection_calls, 1)

    def test_position_size_rejection_blocks_order(self):
        transport = FakeDemoTransport()
        receipt = DemoChallengeExecutor(transport).execute(self.intent(approved=False))
        self.assertFalse(receipt.approved)
        self.assertEqual(receipt.rejection_code, "POSITION_SIZE_NOT_APPROVED")
        self.assertEqual(transport.entry_calls, 0)

    def test_client_order_id_makes_execution_idempotent(self):
        transport = FakeDemoTransport()
        executor = DemoChallengeExecutor(transport)
        first = executor.execute(self.intent())
        second = executor.execute(self.intent())
        self.assertTrue(first.approved)
        self.assertTrue(second.approved)
        self.assertEqual(transport.entry_calls, 1)
        self.assertEqual(second.evidence["idempotent_reuse"], "true")

    def test_protection_retries_once_then_emergency_closes(self):
        transport = FakeDemoTransport()
        transport.protection_results = [
            {"accepted": False, "confirmed": False, "message": "first failure"},
            {"accepted": False, "confirmed": False, "message": "second failure"},
        ]
        receipt = DemoChallengeExecutor(transport).execute(self.intent())
        self.assertFalse(receipt.approved)
        self.assertEqual(receipt.status, DemoOrderStatus.EMERGENCY_CLOSED)
        self.assertEqual(receipt.attempts, 2)
        self.assertEqual(receipt.rejection_code, "PROTECTION_FAILED_EMERGENCY_CLOSE")
        self.assertEqual(transport.close_calls, 1)

    def test_reconciliation_closes_unprotected_position(self):
        transport = FakeDemoTransport()
        intent = self.intent()
        transport.place_market_order(
            {
                "mode": "demo",
                "symbol": intent.symbol,
                "side": "Buy",
                "orderType": "Market",
                "qty": str(intent.size.quantity),
                "clientOrderId": intent.client_order_id,
                "reduceOnly": "false",
            }
        )
        receipt = DemoChallengeExecutor(transport).reconcile(intent)
        self.assertFalse(receipt.approved)
        self.assertEqual(receipt.rejection_code, "UNPROTECTED_POSITION_RECONCILED")
        self.assertEqual(transport.close_calls, 1)


if __name__ == "__main__":
    unittest.main()
