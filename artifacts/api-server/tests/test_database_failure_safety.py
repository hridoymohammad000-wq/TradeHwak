import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.schemas.engine import EngineControlRequest
from app.services.auto_trade_service import AutoTradeService
from app.services.engine_service import EngineService


class UnreadyRepository:
    def __init__(self, reason="database offline"):
        self.reason = reason
        self.saved_workflow_state = None

    def verify_execution_ready(self):
        return False, self.reason

    def load_workflow_state(self):
        return None

    def save_workflow_state(self, state):
        self.saved_workflow_state = state


class ReadySettings:
    def __init__(self):
        self.controls = {
            "scalping_engine_enabled": True,
            "intraday_engine_enabled": False,
            "auto_trade_enabled": False,
            "emergency_stop": False,
        }
        self.updated_controls = None

    def get_control_state(self):
        return dict(self.controls)

    def validate_execution_controls(self, candidate_state):
        return None

    def update_control_state(self, controls):
        self.updated_controls = dict(controls)
        self.controls.update(controls)
        return SimpleNamespace(**self.controls)

    def get_settings_state(self):
        return SimpleNamespace(
            auto_trade_enabled=True,
            daily_max_trades=5,
            daily_max_loss=100.0,
            scalping_engine_enabled=True,
            intraday_engine_enabled=False,
            allowed_signal_grades=[],
        )

    def get_execution_readiness(self):
        return True, None


class ConnectedBybit:
    def get_connection_status(self):
        return SimpleNamespace(data=SimpleNamespace(code="CONNECTED", detail="Connected"))


class TradeSyncSpy:
    def __init__(self):
        self.synced = False

    def sync_with_exchange(self, bybit_service):
        self.synced = True


class DatabaseFailureSafetyTests(unittest.TestCase):
    def test_engine_refuses_to_enable_auto_trade_when_database_is_not_ready(self):
        settings = ReadySettings()
        service = EngineService(
            settings_service=settings,
            bybit_service=ConnectedBybit(),
            repository=UnreadyRepository("missing trade_history"),
        )

        with self.assertRaises(HTTPException) as context:
            service.update_controls(EngineControlRequest(auto_trade_enabled=True))

        self.assertEqual(context.exception.status_code, 503)
        self.assertIn("PostgreSQL persistence is required", context.exception.detail)
        self.assertIn("missing trade_history", context.exception.detail)
        self.assertIsNone(settings.updated_controls)

    def test_auto_trade_cycle_stops_before_exchange_sync_when_database_is_not_ready(self):
        settings = ReadySettings()
        repository = UnreadyRepository("connection refused")
        trade_service = TradeSyncSpy()
        service = AutoTradeService(
            settings_service=settings,
            bybit_service=ConnectedBybit(),
            strategy_service=object(),
            manual_trade_service=object(),
            trade_service=trade_service,
            signal_registry=object(),
            repository=repository,
        )

        result = service.run_cycle()

        self.assertEqual(result, {"status": "database_not_ready", "opened": 0})
        self.assertFalse(trade_service.synced)
        self.assertFalse(settings.updated_controls["auto_trade_enabled"])
        self.assertIn("connection refused", repository.saved_workflow_state["last_reject_reason"])


if __name__ == "__main__":
    unittest.main()
