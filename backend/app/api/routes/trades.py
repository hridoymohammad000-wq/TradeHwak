from datetime import datetime

from fastapi import APIRouter, Query

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
    description="Returns persisted active trades with optional opened-time filtering.",
)
def get_active_trades(
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> ActiveTradesResponse:
    trade_service.sync_with_exchange(bybit_service)
    return trade_service.get_active_trades(start_time=start_time, end_time=end_time)


@router.get(
    "/closed-trades",
    response_model=ClosedTradesResponse,
    summary="Get closed trades",
    description="Returns persisted closed trade journal records with optional close-time filtering.",
)
def get_closed_trades(
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> ClosedTradesResponse:
    trade_service.sync_with_exchange(bybit_service)
    return trade_service.get_closed_trades(start_time=start_time, end_time=end_time)


@router.post(
    "/trade/manual",
    response_model=ManualTradeResponse,
    summary="Submit manual Bybit demo trade",
    description="Places a protected Bybit demo market order using backend risk sizing.",
)
def submit_manual_trade(payload: ManualTradeRequest) -> ManualTradeResponse:
    return manual_trade_service.execute_manual_trade(payload)
