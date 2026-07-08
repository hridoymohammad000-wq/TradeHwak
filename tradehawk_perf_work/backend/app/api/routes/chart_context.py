from fastapi import APIRouter, Query

from app.core.enums import Timeframe, TradingMode
from app.core.state import chart_context_service
from app.schemas.chart_context import ChartContextResponse

router = APIRouter(tags=["Chart"])

@router.get(
    "/chart-context", response_model=ChartContextResponse, summary="Get real chart data",
    description="Returns real closed Bybit Demo candles. Indicator fields remain null unless produced by the backend.",
)
def get_chart_context(
    symbol: str = Query(..., min_length=1, max_length=20),
    mode: TradingMode = Query(...),
    timeframe: Timeframe = Query(default=Timeframe.M15),
    limit: int = Query(default=300, ge=1, le=1000),
) -> ChartContextResponse:
    return chart_context_service.get_context(symbol=symbol, mode=mode, timeframe=timeframe, limit=limit)
