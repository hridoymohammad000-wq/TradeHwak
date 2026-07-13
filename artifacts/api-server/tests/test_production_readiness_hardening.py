from pathlib import Path
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from app import main
from app.schemas.health import HealthData, HealthResponse


class ProductionReadinessHardeningTests(unittest.TestCase):
    @staticmethod
    async def _idle_background_loop():
        return None

    def test_health_route_returns_503_when_system_is_degraded(self):
        degraded = HealthResponse(
            message="Backend status fetched successfully.",
            data=HealthData(
                status="degraded",
                app="TradeHawk Backend",
                phase="operational",
                execution_enabled=False,
                persistence_ready=False,
                bybit_ready=False,
                workers_ready=False,
                worker_status={
                    "auto_trade": {
                        "ready": False,
                        "interval_seconds": 300,
                        "last_error": "worker failure",
                    }
                },
                block_reason="worker failure",
            ),
        )
        with patch.object(main, "_auto_trade_loop", self._idle_background_loop), patch.object(
            main, "_trade_management_loop", self._idle_background_loop
        ), patch.object(main, "_exchange_reconciliation_loop", self._idle_background_loop), patch.object(
            main.settings_service, "reload_from_persistence"
        ), patch.object(
            main.trade_service, "reload_from_persistence"
        ), patch.object(
            main.profit_tracking_service, "reload_from_persistence"
        ), patch.object(
            main.persistence_repository, "initialize"
        ), patch.object(
            main.persistence_repository, "verify_execution_ready", return_value=(True, None)
        ), patch(
            "app.api.routes.health.system_service.get_health",
            return_value=degraded,
        ):
            with TestClient(main.app) as client:
                response = client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["data"]["status"], "degraded")

    def test_render_blueprint_has_no_hardcoded_render_hostname(self):
        render_yaml = (
            Path(__file__).resolve().parents[3] / "render.yaml"
        ).read_text(encoding="utf-8")

        self.assertNotIn("onrender.com", render_yaml)
        self.assertIn("npm run build", render_yaml)


if __name__ == "__main__":
    unittest.main()
