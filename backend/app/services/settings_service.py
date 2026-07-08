from fastapi import HTTPException, status

from app.core.config import get_app_config
from app.core.enums import RuntimeMode, TradingMode
from app.models.settings import TradingSettingsModel
from app.schemas.mode import ModeData, ModeResponse
from app.schemas.settings import (
    EngineControlSection,
    ExecutionControlSection,
    RiskSettingsSection,
    SettingsResponse,
    SettingsStateData,
    SettingsUpdate,
    SettingsViewData,
    StrategySettingsSection,
    SystemSettingsSection,
)
from app.services.runtime_store import RuntimeStore


class SettingsService:
    def __init__(self, runtime_store: RuntimeStore) -> None:
        self._runtime_store = runtime_store
        config = get_app_config()
        default_settings = TradingSettingsModel(
            system_mode=config.default_system_mode,
            active_strategy_mode=config.default_strategy_mode,
        )
        stored_settings = self._runtime_store.get_section("settings", {})
        self._settings = (
            TradingSettingsModel.model_validate(stored_settings)
            if stored_settings
            else default_settings
        )
        self._persist_settings()

    def get_settings_state(self) -> SettingsStateData:
        return SettingsStateData.model_validate(self._settings.model_dump())

    def get_settings_view_data(self) -> SettingsViewData:
        state = self.get_settings_state()
        return SettingsViewData(
            system=SystemSettingsSection(system_mode=state.system_mode),
            strategy=StrategySettingsSection(
                active_strategy_mode=state.active_strategy_mode,
                allowed_signal_grades=state.allowed_signal_grades,
            ),
            risk=RiskSettingsSection(
                daily_max_loss=state.daily_max_loss,
                daily_max_trades=state.daily_max_trades,
                risk_per_trade_pct=state.risk_per_trade_pct,
                max_open_positions=state.max_open_positions,
                scalping=state.scalping,
                intraday=state.intraday,
            ),
            notifications=state.notifications,
            engine_control=EngineControlSection(
                scalping_engine_enabled=state.scalping_engine_enabled,
                intraday_engine_enabled=state.intraday_engine_enabled,
            ),
            execution_control=ExecutionControlSection(
                auto_trade_enabled=state.auto_trade_enabled,
                emergency_stop=state.emergency_stop,
            ),
        )

    def get_settings(self) -> SettingsResponse:
        return SettingsResponse(
            message="Settings fetched successfully.",
            data=self.get_settings_view_data(),
        )

    def get_settings_view(self) -> SettingsResponse:
        return SettingsResponse(
            message="Settings view fetched successfully.",
            data=self.get_settings_view_data(),
        )

    def get_mode_summary(self) -> ModeResponse:
        return ModeResponse(
            message="Mode fetched successfully.",
            data=ModeData(
                system_mode=self._settings.system_mode,
                available_system_modes=[RuntimeMode.DEMO],
                active_strategy_mode=self._settings.active_strategy_mode,
                available_strategy_modes=[
                    TradingMode.SCALPING,
                    TradingMode.INTRADAY,
                ],
            ),
        )

    def update_settings(self, payload: SettingsUpdate) -> SettingsResponse:
        updated_data = self._settings.model_dump()
        patch = payload.model_dump(exclude_unset=True, exclude_none=True)
        notifications_patch = patch.pop("notifications", None)
        scalping_patch = patch.pop("scalping", None)
        intraday_patch = patch.pop("intraday", None)

        updated_data.update(patch)
        if notifications_patch:
            updated_data["notifications"] = {**updated_data["notifications"], **notifications_patch}
        if scalping_patch:
            updated_data["scalping"] = {**updated_data["scalping"], **scalping_patch}
        if intraday_patch:
            updated_data["intraday"] = {**updated_data["intraday"], **intraday_patch}

        candidate = TradingSettingsModel.model_validate(updated_data)
        self._validate_control_state(candidate)
        self._settings = candidate
        self._persist_settings()
        self._runtime_store.append_event(
            "settings_updated",
            "Risk or strategy settings were updated from the control center.",
        )

        return SettingsResponse(
            message="Settings updated successfully.",
            data=self.get_settings_view_data(),
        )

    def get_control_state(self) -> dict[str, bool]:
        return {
            "scalping_engine_enabled": self._settings.scalping_engine_enabled,
            "intraday_engine_enabled": self._settings.intraday_engine_enabled,
            "auto_trade_enabled": self._settings.auto_trade_enabled,
            "emergency_stop": self._settings.emergency_stop,
        }

    def update_control_state(self, controls: dict[str, bool]) -> SettingsStateData:
        updated_data = self._settings.model_dump()
        updated_data.update(controls)
        updated = TradingSettingsModel.model_validate(updated_data)
        self._validate_control_state(updated)
        self._settings = updated
        self._persist_settings()
        self._runtime_store.append_event(
            "engine_control",
            "Execution control state changed on the backend.",
        )
        return self.get_settings_state()

    @staticmethod
    def _validate_control_state(settings: TradingSettingsModel) -> None:
        if settings.emergency_stop and settings.auto_trade_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Auto trade cannot be enabled while emergency stop is active.",
            )

    def _persist_settings(self) -> None:
        self._runtime_store.replace_section(
            "settings",
            self._settings.model_dump(mode="json"),
        )
