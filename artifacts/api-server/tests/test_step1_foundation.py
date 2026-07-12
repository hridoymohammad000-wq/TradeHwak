import unittest

from fastapi import HTTPException

from app.core.enums import RuntimeMode, TradingMode
from app.schemas.settings import SettingsUpdate
from app.services.auto_trade_service import AutoTradeService
from app.services.settings_service import SettingsService
from app.services.system_service import SystemService


class FakeRepository:
    def __init__(self, settings=None, workflow=None):
        self.settings = settings
        self.workflow = workflow
        self.execution_ready = (True, None)

    def load_settings(self):
        return self.settings

    def save_settings(self, settings):
        self.settings = settings

    def load_workflow_state(self):
        return self.workflow

    def save_workflow_state(self, state):
        self.workflow = state

    def verify_execution_ready(self):
        return self.execution_ready


class StepOneFoundationTests(unittest.TestCase):
    def _valid_settings_update(self, **overrides):
        values = {
            "system_mode": RuntimeMode.DEMO,
            "active_strategy_mode": TradingMode.SCALPING,
            "scalping_engine_enabled": True,
            "intraday_engine_enabled": False,
            "auto_trade_enabled": True,
            "emergency_stop": False,
            "risk_per_trade_pct": 1.0,
            "daily_max_loss": 100.0,
            "max_open_positions": 2,
            "daily_max_trades": 5,
        }
        values.update(overrides)
        return SettingsUpdate(**values)

    def test_auto_trade_requires_the_selected_engine(self):
        service = SettingsService(repository=FakeRepository())

        with self.assertRaises(HTTPException) as context:
            service.update_settings(
                self._valid_settings_update(
                    scalping_engine_enabled=False,
                    intraday_engine_enabled=True,
                )
            )

        self.assertEqual(context.exception.detail, "Scalping engine is disabled.")

    def test_auto_trade_requires_positive_canonical_risk_limits(self):
        service = SettingsService(repository=FakeRepository())

        with self.assertRaises(HTTPException) as context:
            service.update_settings(
                self._valid_settings_update(daily_max_trades=0)
            )

        self.assertIn("Set daily max trades above 0", context.exception.detail)

    def test_canonical_risk_fields_override_user_edits(self):
        service = SettingsService(repository=FakeRepository())

        updated = service.update_settings(
            self._valid_settings_update(
                active_strategy_mode=TradingMode.INTRADAY,
                scalping_engine_enabled=False,
                intraday_engine_enabled=True,
                risk_per_trade_pct=99.0,
                daily_max_loss=999.0,
                max_open_positions=99,
                daily_max_trades=7,
            )
        )

        self.assertEqual(updated.data.risk.daily_max_trades, 7)
        self.assertEqual(updated.data.risk.daily_max_loss, 5.0)
        self.assertEqual(updated.data.risk.max_open_positions, 5)
        self.assertEqual(updated.data.risk.risk_per_trade_pct, 1.0)

    def test_health_execution_flag_uses_persisted_settings_readiness(self):
        service = SettingsService(repository=FakeRepository())
        service.update_settings(self._valid_settings_update())
        repository = FakeRepository()
        health = SystemService(
            settings_service=service,
            repository=repository,
        ).get_health()

        self.assertTrue(health.data.execution_enabled)
        self.assertEqual(health.data.phase, "operational")
        self.assertTrue(health.data.persistence_ready)
        self.assertIsNone(health.data.block_reason)

        service.update_settings(SettingsUpdate(auto_trade_enabled=False))
        health = SystemService(
            settings_service=service,
            repository=repository,
        ).get_health()
        self.assertFalse(health.data.execution_enabled)

    def test_invalid_persisted_auto_trade_state_is_safely_disabled(self):
        repository = FakeRepository(
            settings={
                "system_mode": "demo",
                "active_strategy_mode": "scalping",
                "scalping_engine_enabled": False,
                "intraday_engine_enabled": True,
                "auto_trade_enabled": True,
                "emergency_stop": False,
                "daily_max_loss": 0.0,
                "daily_max_trades": 5,
                "risk_per_trade_pct": 1.0,
                "max_open_positions": 2,
                "allowed_signal_grades": ["A+", "A"],
                "notifications": {
                    "telegram": False,
                    "email": False,
                    "chime": True,
                    "toast": True,
                },
            }
        )
        service = SettingsService(repository=repository)
        service.reload_from_persistence()

        self.assertFalse(service.get_settings_state().auto_trade_enabled)
        self.assertFalse(repository.settings["auto_trade_enabled"])

    def test_health_is_degraded_when_persistence_is_not_ready(self):
        repository = FakeRepository()
        repository.execution_ready = (False, "DATABASE_URL is not configured.")
        service = SettingsService(repository=repository)
        health = SystemService(
            settings_service=service,
            repository=repository,
        ).get_health()

        self.assertEqual(health.data.status, "degraded")
        self.assertFalse(health.data.persistence_ready)
        self.assertEqual(
            health.data.block_reason,
            "DATABASE_URL is not configured.",
        )

    def test_workflow_snapshot_restores_and_persists(self):
        repository = FakeRepository(
            workflow={
                "scanner_status": "scanned_12_symbols",
                "signal_status": "candidate_ready",
                "execution_status": "rejected",
                "candidate_signal": {
                    "symbol": "BTCUSDT",
                    "direction": "BUY",
                    "grade": "A+",
                    "timeframe": "M5",
                    "reason": "test",
                },
                "last_order": None,
                "last_reject_reason": "test rejection",
                "last_cycle_at": "2026-07-09T00:00:00+00:00",
            }
        )
        settings = SettingsService(repository=FakeRepository())
        service = AutoTradeService(
            settings_service=settings,
            bybit_service=object(),
            strategy_service=object(),
            manual_trade_service=object(),
            trade_service=object(),
            signal_registry=object(),
            repository=repository,
        )

        self.assertEqual(service._last_scanner_status, "scanned_12_symbols")
        self.assertEqual(service._last_candidate_signal.symbol, "BTCUSDT")

        service._last_execution_status = "submitted"
        service._persist_state()
        self.assertEqual(repository.workflow["execution_status"], "submitted")


if __name__ == "__main__":
    unittest.main()
