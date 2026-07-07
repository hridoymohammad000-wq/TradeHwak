from pydantic import BaseModel

from app.core.enums import Direction, RuntimeMode, Timeframe, TradingMode
from app.schemas.common import ApiResponse


class TodaySummary(BaseModel):
    total_open_trades: int
    scalping_open_trades: int
    intraday_open_trades: int
    closed_trades_today: int
    system_mode: RuntimeMode


class ActiveTradeRecord(BaseModel):
    symbol: str
    mode: TradingMode
    direction: Direction
    qty: str | None = None
    entry_price: float | None = None
    current_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    notional: float | None = None
    planned_risk_usdt: float | None = None
    risk_reward: float | None = None
    pnl: float | None = None
    status: str
    timeframe: Timeframe | None = None
    opened_at: str | None = None


class ClosedTradeRecord(BaseModel):
    symbol: str
    mode: TradingMode
    direction: Direction
    qty: str | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    notional: float | None = None
    planned_risk_usdt: float | None = None
    realized_pnl: float | None = None
    risk_reward: float | None = None
    result: str | None = None
    status: str
    close_reason: str | None = None
    exit_analysis: str | None = None
    timeframe: Timeframe | None = None
    closed_time: str | None = None


class ActiveTradesData(BaseModel):
    today_summary: TodaySummary
    scalping_trades: list[ActiveTradeRecord]
    intraday_trades: list[ActiveTradeRecord]


class ActiveTradesResponse(ApiResponse[ActiveTradesData]):
    data: ActiveTradesData


class ClosedTradesData(BaseModel):
    closed_trades: list[ClosedTradeRecord]


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
    risk_reward: float
    notional: float


class ManualTradeResponse(ApiResponse[ManualTradeData]):
    data: ManualTradeData
