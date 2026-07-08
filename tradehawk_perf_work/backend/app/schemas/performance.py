from pydantic import BaseModel
from app.schemas.common import ApiResponse
from app.schemas.trades import ClosedTradeRecord

class PerformanceSummary(BaseModel):
    total_trades:int
    wins:int
    losses:int
    breakeven:int
    realized_pnl:float|None=None
    average_realized_pnl:float|None=None
    win_rate:float|None=None
    average_risk_reward:float|None=None
    best_trade:float|None=None
    worst_trade:float|None=None
    stop_loss_hit_count:int
    take_profit_hit_count:int
    manual_close_count:int
    emergency_stop_count:int

class PerformanceSummaries(BaseModel):
    scalping:PerformanceSummary
    intraday:PerformanceSummary
    unknown:PerformanceSummary
    combined:PerformanceSummary

class PerformanceData(BaseModel):
    trades:list[ClosedTradeRecord]
    summaries:PerformanceSummaries
    strategies:list[str]
    statuses:list[str]
    exit_reasons:list[str]
    range_start:str|None=None
    range_end:str|None=None

class PerformanceResponse(ApiResponse[PerformanceData]):
    data:PerformanceData
