from pydantic import BaseModel

from app.core.enums import Direction, RuntimeMode, Timeframe, TradingMode
from app.schemas.common import ApiResponse


class TodaySummary(BaseModel):
    total_open_trades: int
    scalping_open_trades: int
    intraday_open_trades: int
    unknown_open_trades: int = 0
    closed_trades_today: int
    system_mode: RuntimeMode


class ActiveTradeRecord(BaseModel):
    trade_id: str
    order_id: str | None = None
    signal_id: str | None = None
    symbol: str
    mode: TradingMode | None = None
    direction: Direction
    qty: str | None = None
    entry_price: float | None = None
    current_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    notional: float | None = None
    planned_risk_usdt: float | None = None
    risk_distance: float | None = None
    risk_pct_of_entry: float | None = None
    risk_reward: float | None = None
    pnl: float | None = None
    status: str
    timeframe: Timeframe | None = None
    opened_at: str | None = None


class ClosedTradeRecord(BaseModel):
    trade_id: str
    order_id: str | None = None
    signal_id: str | None = None
    symbol: str
    mode: TradingMode | None = None
    direction: Direction
    qty: str | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    notional: float | None = None
    planned_risk_usdt: float | None = None
    risk_distance: float | None = None
    risk_pct_of_entry: float | None = None
    realized_pnl: float | None = None
    pnl_multiple_of_risk: float | None = None
    stop_slippage_usdt: float | None = None
    risk_reward: float | None = None
    result: str | None = None
    status: str
    close_reason: str | None = None
    exit_analysis: str | None = None
    operator_summary: str | None = None
    timeframe: Timeframe | None = None
    opened_at: str | None = None
    closed_time: str | None = None


class JournalSummary(BaseModel):
    total_trades: int
    wins: int
    losses: int
    win_rate: float | None = None
    realized_pnl: float | None = None
    average_risk_reward: float | None = None


class JournalSummaries(BaseModel):
    scalping: JournalSummary
    intraday: JournalSummary
    unknown: JournalSummary
    combined: JournalSummary


class ActiveTradesData(BaseModel):
    today_summary: TodaySummary
    active_trades: list[ActiveTradeRecord]
    scalping_trades: list[ActiveTradeRecord]
    intraday_trades: list[ActiveTradeRecord]
    unknown_trades: list[ActiveTradeRecord]
    range_start: str | None = None
    range_end: str | None = None


class ActiveTradesResponse(ApiResponse[ActiveTradesData]):
    data: ActiveTradesData


class ClosedTradesData(BaseModel):
    closed_trades: list[ClosedTradeRecord]
    summaries: JournalSummaries
    range_start: str | None = None
    range_end: str | None = None


class ClosedTradesResponse(ApiResponse[ClosedTradesData]):
    data: ClosedTradesData


class ManualTradeRequest(BaseModel):
    symbol: str
    direction: Direction
    mode: TradingMode
    timeframe: Timeframe | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


class ManualTradeData(BaseModel):
    status: str
    order_id: str | None = None
    symbol: str
    side: str
    qty: str
    market_price: float
    stop_loss: float
    take_profit: float
    planned_risk_usdt: float
    risk_distance: float
    risk_pct_of_entry: float
    risk_reward: float
    notional: float


class ManualTradeResponse(ApiResponse[ManualTradeData]):
    data: ManualTradeData
