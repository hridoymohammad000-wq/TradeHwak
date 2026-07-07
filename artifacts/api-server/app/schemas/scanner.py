from pydantic import BaseModel, Field, field_validator

from app.core.enums import Direction, SignalGrade, Timeframe, TradingMode
from app.schemas.common import ApiResponse


class ScanRequest(BaseModel):
    mode: TradingMode | None = None
    symbols: list[str] = Field(default_factory=list, max_length=25)
    timeframe: Timeframe | None = None
    direction: Direction | None = None
    grade: SignalGrade | None = None

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        normalized = []
        for symbol in value:
            clean_symbol = symbol.strip().upper()
            if not clean_symbol:
                raise ValueError("Symbols must not contain blank values.")
            normalized.append(clean_symbol)
        return normalized


class ScanResult(BaseModel):
    symbol: str
    mode: TradingMode
    timeframe: Timeframe | None = None
    direction: Direction | None = None
    grade: SignalGrade | None = None
    reason: str | None = None


class ScanData(BaseModel):
    mode: TradingMode
    timeframe: Timeframe | None = None
    results: list[ScanResult]


class ScanResponse(ApiResponse[ScanData]):
    data: ScanData
