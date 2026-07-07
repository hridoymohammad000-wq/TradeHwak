from pydantic import BaseModel

from app.core.enums import ChartStatus, Timeframe, TradingMode
from app.schemas.common import ApiResponse


class IndicatorContext(BaseModel):
    ema20: float | None = None
    ema50: float | None = None
    ema200: float | None = None
    rsi: float | None = None


class ChartContextData(BaseModel):
    symbol: str
    mode: TradingMode
    timeframe: Timeframe | None = None
    chart_status: ChartStatus
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward: float | None = None
    indicator_context: IndicatorContext


class ChartContextResponse(ApiResponse[ChartContextData]):
    data: ChartContextData
