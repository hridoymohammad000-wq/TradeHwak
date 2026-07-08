from app.core.config import get_app_config
from app.schemas.health import HealthData, HealthResponse


class SystemService:
    def __init__(self) -> None:
        self._config = get_app_config()

    def get_health(self) -> HealthResponse:
        return HealthResponse(
            message="Backend status fetched successfully.",
            data=HealthData(
                status="healthy",
                app=self._config.app_name,
                phase=self._config.phase,
                execution_enabled=self._config.execution_enabled,
            ),
        )
