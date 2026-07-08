from pydantic import BaseModel, Field

from app.core.enums import ChartStatus, Timeframe, TradingMode
from app.schemas.common import ApiResponse


class ChartCandle(BaseModel):
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    turnover: float | None = None


class IndicatorContext(BaseModel):
    ema20: float | None = None
    ema50: float | None = None
    ema200: float | None = None
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None


class ChartContextData(BaseModel):
    symbol: str
    mode: TradingMode
    timeframe: Timeframe
    chart_status: ChartStatus
    candles: list[ChartCandle] = Field(default_factory=list)
    last_price: float | None = None
    indicator_context: IndicatorContext = Field(default_factory=IndicatorContext)
    fetched_at: str | None = None


class ChartContextResponse(ApiResponse[ChartContextData]):
    data: ChartContextData
