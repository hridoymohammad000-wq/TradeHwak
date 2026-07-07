from fastapi import APIRouter, Query

from app.core.enums import Timeframe, TradingMode
from app.core.state import chart_context_service
from app.schemas.chart_context import ChartContextResponse


router = APIRouter(tags=["Chart"])


@router.get(
    "/chart-context",
    response_model=ChartContextResponse,
    summary="Get chart context",
    description="Returns validated chart workspace context with placeholder indicator values.",
)
def get_chart_context(
    symbol: str = Query(..., min_length=1, max_length=20),
    mode: TradingMode = Query(...),
    timeframe: Timeframe | None = Query(default=None),
) -> ChartContextResponse:
    return chart_context_service.get_context(
        symbol=symbol,
        mode=mode,
        timeframe=timeframe,
    )
