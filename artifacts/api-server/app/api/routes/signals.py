from fastapi import APIRouter, Query

from app.core.enums import SignalGrade, Timeframe, TradingMode
from app.core.state import persistence_repository, signals_service
from app.schemas.signals import SignalsResponse


router = APIRouter(tags=["Signals"])


@router.get(
    "/signals",
    response_model=SignalsResponse,
    summary="Get signals",
    description="Returns signal results and the effective frontend filters.",
)
def get_signals(
    mode: TradingMode | None = Query(default=None),
    grade: SignalGrade | None = Query(default=None),
    symbol: str | None = Query(default=None, min_length=1, max_length=20),
    timeframe: Timeframe | None = Query(default=None),
) -> SignalsResponse:
    normalized_symbol = symbol.strip().upper() if symbol else None
    response = signals_service.get_signals(mode, grade, normalized_symbol, timeframe)
    persistence_repository.append_log("signal_logs", "signals_fetched", response.model_dump(mode="json"))
    return response
