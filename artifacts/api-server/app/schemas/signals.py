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
    status: str
    entry_price: float | None = None
    current_price: float | None = None


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
