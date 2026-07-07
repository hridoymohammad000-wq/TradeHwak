from pydantic import BaseModel

from app.core.enums import RuntimeMode, SystemStatus, TradingMode
from app.schemas.common import ApiResponse


class DashboardTodaySummary(BaseModel):
    total_open_trades: int
    closed_trades_today: int


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
    today_summary: DashboardTodaySummary
    recent_events: list[DashboardEvent]


class DashboardSummaryResponse(ApiResponse[DashboardSummaryData]):
    data: DashboardSummaryData
