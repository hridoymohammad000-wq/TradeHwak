from app.core.config import get_app_config
from app.schemas.health import HealthData, HealthResponse
from app.services.settings_service import SettingsService


class SystemService:
    def __init__(self, settings_service: SettingsService | None = None) -> None:
        self._config = get_app_config()
        self._settings_service = settings_service

    def get_health(self) -> HealthResponse:
        execution_enabled = self._config.execution_enabled
        if self._settings_service is not None:
            execution_enabled, _ = self._settings_service.get_execution_readiness()

        return HealthResponse(
            message="Backend status fetched successfully.",
            data=HealthData(
                status="healthy",
                app=self._config.app_name,
                phase=self._config.phase,
                execution_enabled=execution_enabled,
            ),
        )
