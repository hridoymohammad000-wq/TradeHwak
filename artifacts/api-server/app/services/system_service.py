from fastapi import HTTPException

from app.core.config import get_app_config
from app.db.repository import PersistenceRepository
from app.schemas.health import HealthData, HealthResponse
from app.services.runtime_health_service import RuntimeHealthService
from app.services.settings_service import SettingsService


class SystemService:
    def __init__(
        self,
        settings_service: SettingsService | None = None,
        repository: PersistenceRepository | None = None,
        bybit_service=None,
        runtime_health_service: RuntimeHealthService | None = None,
    ) -> None:
        self._config = get_app_config()
        self._settings_service = settings_service
        self._repository = repository
        self._bybit_service = bybit_service
        self._runtime_health_service = runtime_health_service

    def get_health(self) -> HealthResponse:
        execution_enabled = self._config.execution_enabled
        persistence_ready: bool | None = None
        bybit_ready: bool | None = None
        workers_ready: bool | None = None
        worker_status: dict[str, dict[str, bool | str | int | None]] = {}
        block_reason: str | None = None
        if self._settings_service is not None:
            execution_enabled, _ = self._settings_service.get_execution_readiness()
        if self._repository is not None:
            checker = getattr(self._repository, "verify_execution_ready", None)
            if callable(checker):
                persistence_ready, block_reason = checker()
        if self._bybit_service is not None:
            try:
                connection = self._bybit_service.get_connection_status()
                bybit_ready = connection.data.code == "CONNECTED"
                if not bybit_ready and block_reason is None:
                    block_reason = connection.data.detail
            except HTTPException as exc:
                bybit_ready = False
                if block_reason is None:
                    block_reason = str(exc.detail)
        if self._runtime_health_service is not None:
            worker_status = self._runtime_health_service.snapshot()
            workers_ready = all(
                bool(worker.get("ready"))
                for worker in worker_status.values()
            ) if worker_status else None
            if workers_ready is False and block_reason is None:
                failing = next(
                    (
                        name
                        for name, worker in worker_status.items()
                        if not worker.get("ready")
                    ),
                    "workers",
                )
                worker_error = worker_status.get(failing, {}).get("last_error")
                block_reason = (
                    f"{failing} worker is not healthy: {worker_error}"
                    if worker_error
                    else f"{failing} worker is not healthy."
                )

        overall_healthy = all(
            value is not False
            for value in (persistence_ready, bybit_ready, workers_ready)
        )

        return HealthResponse(
            message="Backend status fetched successfully.",
            data=HealthData(
                status="healthy" if overall_healthy else "degraded",
                app=self._config.app_name,
                phase=self._config.phase,
                execution_enabled=execution_enabled,
                persistence_ready=persistence_ready,
                bybit_ready=bybit_ready,
                workers_ready=workers_ready,
                worker_status=worker_status,
                block_reason=block_reason,
            ),
        )
