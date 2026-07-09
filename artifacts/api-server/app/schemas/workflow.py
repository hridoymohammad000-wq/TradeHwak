from pydantic import BaseModel

from app.core.enums import TradingMode
from app.schemas.common import ApiResponse


class WorkflowSignalSnapshot(BaseModel):
    symbol: str
    direction: str
    grade: str
    timeframe: str
    reason: str


class WorkflowOrderSnapshot(BaseModel):
    symbol: str
    side: str
    qty: str
    order_id: str | None = None
    status: str


class WorkflowStatusData(BaseModel):
    backend_health: str
    selected_mode: TradingMode
    scanner_status: str
    signal_status: str
    execution_status: str
    execution_ready: bool = False
    execution_block_reason: str | None = None
    auto_trade_enabled: bool
    bybit_connection_code: str
    active_trade_count: int
    daily_trade_count: int
    candidate_signal: WorkflowSignalSnapshot | None = None
    last_order: WorkflowOrderSnapshot | None = None
    last_reject_reason: str | None = None
    last_cycle_at: str | None = None


class WorkflowStatusResponse(ApiResponse[WorkflowStatusData]):
    data: WorkflowStatusData
