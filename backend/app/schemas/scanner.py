from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.enums import Direction, SignalGrade, Timeframe, TradingMode
from app.schemas.common import ApiResponse


ScanOutcome = Literal["actionable", "rejected", "skipped", "failed"]


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


class ScanMetrics(BaseModel):
    current_price: float | None = None
    ema20: float | None = None
    ema50: float | None = None
    rsi14: float | None = None
    trend_gap_pct: float | None = None


class ScanResult(BaseModel):
    symbol: str
    outcome: ScanOutcome
    mode: TradingMode
    timeframe: Timeframe | None = None
    direction: Direction | None = None
    grade: SignalGrade | None = None
    strategy: str | None = None
    reason: str | None = None
    rejection_reason: str | None = None
    failure_reason: str | None = None
    metrics: ScanMetrics | None = None


class ScanCounts(BaseModel):
    total: int = 0
    actionable: int = 0
    rejected: int = 0
    skipped: int = 0
    failed: int = 0


class ScanData(BaseModel):
    mode: TradingMode
    timeframe: Timeframe | None = None
    counts: ScanCounts
    results: list[ScanResult]


class ScanResponse(ApiResponse[ScanData]):
    data: ScanData
