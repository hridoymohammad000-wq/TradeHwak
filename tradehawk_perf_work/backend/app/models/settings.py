from pydantic import BaseModel, Field, model_validator

from app.core.enums import RuntimeMode, SignalGrade, TradingMode

class NotificationSettingsModel(BaseModel):
    telegram: bool = False
    email: bool = False
    chime: bool = True
    toast: bool = True

class ModeRiskSettingsModel(BaseModel):
    max_risk_per_trade_pct: float = Field(default=0.0, ge=0, le=100)
    max_trades_per_day: int = Field(default=0, ge=0)
    max_daily_loss: float = Field(default=0.0, ge=0)
    max_concurrent_trades: int = Field(default=0, ge=0)
    session_start_utc: str | None = None
    session_end_utc: str | None = None

class TradingSettingsModel(BaseModel):
    system_mode: RuntimeMode = RuntimeMode.DEMO
    active_strategy_mode: TradingMode = TradingMode.SCALPING
    scalping_engine_enabled: bool = False
    intraday_engine_enabled: bool = False
    auto_trade_enabled: bool = False
    emergency_stop: bool = False
    daily_max_loss: float = Field(default=0.0, ge=0)
    daily_max_trades: int = Field(default=0, ge=0)
    risk_per_trade_pct: float = Field(default=0.0, ge=0, le=100)
    max_open_positions: int = Field(default=0, ge=0)
    scalping: ModeRiskSettingsModel | None = None
    intraday: ModeRiskSettingsModel | None = None
    allowed_signal_grades: list[SignalGrade] = Field(default_factory=lambda: [SignalGrade.A_PLUS, SignalGrade.A])
    notifications: NotificationSettingsModel = Field(default_factory=NotificationSettingsModel)

    @model_validator(mode="after")
    def migrate_mode_profiles(self) -> "TradingSettingsModel":
        baseline = ModeRiskSettingsModel(
            max_risk_per_trade_pct=self.risk_per_trade_pct,
            max_trades_per_day=self.daily_max_trades,
            max_daily_loss=self.daily_max_loss,
            max_concurrent_trades=self.max_open_positions,
        )
        if self.scalping is None:
            self.scalping = baseline.model_copy(deep=True)
        if self.intraday is None:
            self.intraday = baseline.model_copy(deep=True)
        return self
