from pydantic import BaseModel

from app.core.enums import Direction, SignalGrade, Timeframe, TradingMode
from app.schemas.common import ApiResponse


class SignalItem(BaseModel):
    signal_id: str
    symbol: str
    direction: Direction
    grade: SignalGrade
    mode: TradingMode
    timeframe: Timeframe
    higher_timeframe: str | None = None
    status: str
    strategy: str
    reason: str
    entry_price: float | None = None
    current_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward: float | None = None
    score: float | None = None
    confidence: float | None = None
    htf_score: float | None = None


class SignalFilters(BaseModel):
    mode: TradingMode
    grade: SignalGrade | None = None
    symbol: str | None = None
    timeframe: Timeframe | None = None


class SignalsData(BaseModel):
    filters: SignalFilters
    signals: list[SignalItem]


class SignalsResponse(ApiResponse[SignalsData]):
    data: SignalsData
