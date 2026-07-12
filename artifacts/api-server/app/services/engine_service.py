from fastapi import HTTPException, status

from app.schemas.engine import (
    EngineControlRequest,
    EngineControlResponse,
    EngineControlState,
)
from app.db.repository import PersistenceRepository
from app.services.bybit_service import BybitService
from app.services.settings_service import SettingsService


class EngineService:
    def __init__(
        self,
        settings_service: SettingsService,
        bybit_service: BybitService,
        repository: PersistenceRepository | None = None,
    ) -> None:
        self._settings_service = settings_service
        self._bybit_service = bybit_service
        self._repository = repository

    def update_controls(self, payload: EngineControlRequest) -> EngineControlResponse:
        current_state = self._settings_service.get_control_state()
        updates = payload.model_dump(exclude_unset=True, exclude_none=True)
        candidate_state = {**current_state, **updates}

        if updates.get("emergency_stop") is True:
            candidate_state["auto_trade_enabled"] = False

        if (
            candidate_state["emergency_stop"]
            and updates.get("auto_trade_enabled") is True
            and updates.get("emergency_stop") is not False
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Release emergency stop before enabling auto trade.",
            )

        if updates.get("auto_trade_enabled") is True:
            self._validate_auto_trade_gate(candidate_state)

        settings = self._settings_service.update_control_state(candidate_state)
        return EngineControlResponse(
            message="Engine control updated successfully.",
            data=EngineControlState(
                scalping_engine_enabled=settings.scalping_engine_enabled,
                intraday_engine_enabled=settings.intraday_engine_enabled,
                auto_trade_enabled=settings.auto_trade_enabled,
                emergency_stop=settings.emergency_stop,
            ),
        )

    def _validate_auto_trade_gate(self, candidate_state: dict[str, bool]) -> None:
        self._settings_service.validate_execution_controls(candidate_state)
        self._validate_persistence_ready()

        bybit_status = self._bybit_service.get_connection_status().data
        if bybit_status.code != "CONNECTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bybit Demo must be connected before enabling auto trade.",
            )

    def _validate_persistence_ready(self) -> None:
        if self._repository is None:
            return

        checker = getattr(self._repository, "verify_execution_ready", None)
        if not callable(checker):
            return

        ready, reason = checker()
        if ready:
            return

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"PostgreSQL persistence is required before auto trade can start: {reason}",
        )
