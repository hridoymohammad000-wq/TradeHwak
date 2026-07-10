from pydantic import BaseModel

from app.core.enums import RuntimeMode, SystemStatus, TradingMode
from app.schemas.common import ApiResponse


class DashboardAccount(BaseModel):
    status: str
    equity: float | None = None
    available_balance: float | None = None


class DashboardTodaySummary(BaseModel):
    total_open_trades: int
    scalping_open_trades: int
    intraday_open_trades: int
    unknown_open_trades: int = 0
    closed_trades_today: int
    wins_today: int = 0
    losses_today: int = 0
    win_rate_today: float | None = None
    unrealized_pnl: float | None = None
    realized_pnl_today: float | None = None
    average_risk_reward_today: float | None = None


class DashboardProfitTracking(BaseModel):
    trading_day: str
    week_start: str
    daily_target_pct: float
    weekly_target_pct: float
    daily_realized_pnl: float
    daily_realized_pct: float
    daily_peak_profit_pct: float
    daily_locked_floor_pct: float
    weekly_realized_pnl: float
    weekly_realized_pct: float
    weekly_peak_profit_pct: float
    updated_at: str | None = None


class DashboardEvent(BaseModel):
    event_type: str
    message: str
    created_at: str | None = None


class DashboardSummaryData(BaseModel):
    system_status: SystemStatus
    system_mode: RuntimeMode
    active_strategy_mode: TradingMode
    scalping_engine_enabled: bool
    intraday_engine_enabled: bool
    auto_trade_enabled: bool
    emergency_stop: bool
    account: DashboardAccount
    today_summary: DashboardTodaySummary
    profit_tracking: DashboardProfitTracking
    recent_events: list[DashboardEvent]


class DashboardSummaryResponse(ApiResponse[DashboardSummaryData]):
    data: DashboardSummaryData
