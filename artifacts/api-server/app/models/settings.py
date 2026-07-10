from pydantic import BaseModel, Field

from app.core.enums import RuntimeMode, SignalGrade, TradingMode


class NotificationSettingsModel(BaseModel):
    telegram: bool = False
    email: bool = False
    chime: bool = True
    toast: bool = True


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
    max_open_positions: int = Field(default=5, ge=1)
    allowed_signal_grades: list[SignalGrade] = Field(
        default_factory=lambda: [SignalGrade.A_PLUS, SignalGrade.A]
    )
    notifications: NotificationSettingsModel = Field(
        default_factory=NotificationSettingsModel
    )
