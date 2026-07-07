from fastapi import APIRouter

from app.core.state import bybit_service, manual_trade_service, trade_service
from app.schemas.trades import (
    ActiveTradesResponse,
    ClosedTradesResponse,
    ManualTradeRequest,
    ManualTradeResponse,
)


router = APIRouter(tags=["Trades"])


@router.get(
    "/active-trades",
    response_model=ActiveTradesResponse,
    summary="Get active trades",
    description="Returns frontend-safe active trade sections for scalping and intraday modes.",
)
def get_active_trades() -> ActiveTradesResponse:
    trade_service.sync_with_exchange(bybit_service)
    return trade_service.get_active_trades()


@router.get(
    "/closed-trades",
    response_model=ClosedTradesResponse,
    summary="Get closed trades",
    description="Returns an empty-safe journal structure for closed trades history.",
)
def get_closed_trades() -> ClosedTradesResponse:
    trade_service.sync_with_exchange(bybit_service)
    return trade_service.get_closed_trades()


@router.post(
    "/trade/manual",
    response_model=ManualTradeResponse,
    summary="Submit manual Bybit demo trade",
    description="Places a protected Bybit demo market order using backend risk sizing.",
)
def submit_manual_trade(payload: ManualTradeRequest) -> ManualTradeResponse:
    return manual_trade_service.execute_manual_trade(payload)
