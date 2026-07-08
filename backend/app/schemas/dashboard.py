from pydantic import BaseModel

from app.core.enums import RuntimeMode, SystemStatus, TradingMode
from app.schemas.common import ApiResponse


class DashboardAccountSummary(BaseModel):
    status: str
    equity: float | None = None
    available_balance: float | None = None


class DashboardTodaySummary(BaseModel):
    total_open_trades: int
    scalping_open_trades: int
    intraday_open_trades: int
    unknown_open_trades: int
    closed_trades_today: int
    wins_today: int
    losses_today: int
    win_rate_today: float | None = None
    unrealized_pnl: float | None = None
    realized_pnl_today: float | None = None
    average_risk_reward_today: float | None = None


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
    account: DashboardAccountSummary
    today_summary: DashboardTodaySummary
    recent_events: list[DashboardEvent]
    range_start: str | None = None
    range_end: str | None = None


class DashboardSummaryResponse(ApiResponse[DashboardSummaryData]):
    data: DashboardSummaryData
