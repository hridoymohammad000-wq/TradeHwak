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

    def load_settings(self):
        return self.settings

    def save_settings(self, settings):
        self.settings = settings

    def load_workflow_state(self):
        return self.workflow

    def save_workflow_state(self, state):
        self.workflow = state


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
        cases = (
            ("daily_max_loss", "Set daily max loss above 0 USDT"),
            ("daily_max_trades", "Set daily max trades above 0"),
            ("max_open_positions", "Set max open positions above 0"),
        )
        for field, expected in cases:
            with self.subTest(field=field):
                service = SettingsService(repository=FakeRepository())
                with self.assertRaises(HTTPException) as context:
                    service.update_settings(
                        self._valid_settings_update(**{field: 0})
                    )
                self.assertIn(expected, context.exception.detail)

    def test_health_execution_flag_uses_persisted_settings_readiness(self):
        service = SettingsService(repository=FakeRepository())
        service.update_settings(self._valid_settings_update())
        health = SystemService(settings_service=service).get_health()

        self.assertTrue(health.data.execution_enabled)
        self.assertEqual(health.data.phase, "operational")

        service.update_settings(SettingsUpdate(auto_trade_enabled=False))
        health = SystemService(settings_service=service).get_health()
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
