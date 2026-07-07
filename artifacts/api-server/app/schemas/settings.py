from pydantic import BaseModel, Field, model_validator

from app.core.enums import RuntimeMode, SignalGrade, TradingMode
from app.schemas.common import ApiResponse


class NotificationSettings(BaseModel):
    telegram: bool = False
    email: bool = False
    chime: bool = True
    toast: bool = True


class NotificationSettingsUpdate(BaseModel):
    telegram: bool | None = None
    email: bool | None = None
    chime: bool | None = None
    toast: bool | None = None

    @model_validator(mode="after")
    def validate_not_empty(self) -> "NotificationSettingsUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one notification setting must be provided.")
        return self


class SettingsStateData(BaseModel):
    system_mode: RuntimeMode
    active_strategy_mode: TradingMode
    scalping_engine_enabled: bool
    intraday_engine_enabled: bool
    auto_trade_enabled: bool
    emergency_stop: bool
    daily_max_loss: float = Field(ge=0)
    daily_max_trades: int = Field(ge=0)
    risk_per_trade_pct: float = Field(ge=0, le=100)
    max_open_positions: int = Field(ge=0)
    allowed_signal_grades: list[SignalGrade]
    notifications: NotificationSettings


class SystemSettingsSection(BaseModel):
    system_mode: RuntimeMode


class StrategySettingsSection(BaseModel):
    active_strategy_mode: TradingMode
    allowed_signal_grades: list[SignalGrade]


class RiskSettingsSection(BaseModel):
    daily_max_loss: float = Field(ge=0)
    daily_max_trades: int = Field(ge=0)
    risk_per_trade_pct: float = Field(ge=0, le=100)
    max_open_positions: int = Field(ge=0)


class EngineControlSection(BaseModel):
    scalping_engine_enabled: bool
    intraday_engine_enabled: bool


class ExecutionControlSection(BaseModel):
    auto_trade_enabled: bool
    emergency_stop: bool


class SettingsViewData(BaseModel):
    system: SystemSettingsSection
    strategy: StrategySettingsSection
    risk: RiskSettingsSection
    notifications: NotificationSettings
    engine_control: EngineControlSection
    execution_control: ExecutionControlSection


class SettingsUpdate(BaseModel):
    system_mode: RuntimeMode | None = None
    active_strategy_mode: TradingMode | None = None
    scalping_engine_enabled: bool | None = None
    intraday_engine_enabled: bool | None = None
    auto_trade_enabled: bool | None = None
    emergency_stop: bool | None = None
    daily_max_loss: float | None = Field(default=None, ge=0)
    daily_max_trades: int | None = Field(default=None, ge=0)
    risk_per_trade_pct: float | None = Field(default=None, ge=0, le=100)
    max_open_positions: int | None = Field(default=None, ge=0)
    allowed_signal_grades: list[SignalGrade] | None = None
    notifications: NotificationSettingsUpdate | None = None

    @model_validator(mode="after")
    def validate_not_empty(self) -> "SettingsUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one settings field must be provided.")
        return self


class SettingsResponse(ApiResponse[SettingsViewData]):
    data: SettingsViewData
