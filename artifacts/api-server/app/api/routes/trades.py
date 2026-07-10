from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.core.state import bybit_service, manual_trade_service, trade_service
from app.schemas.trades import (
    ActiveTradesResponse,
    ClosedTradesResponse,
    ManualTradeRequest,
    ManualTradeResponse,
)


router = APIRouter(tags=["Trades"])


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
def get_closed_trades(
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
) -> ClosedTradesResponse:
    trade_service.sync_with_exchange(bybit_service)
    response = trade_service.get_closed_trades()

    start = _parse_datetime(start_time)
    end = _parse_datetime(end_time)
    if start is None and end is None:
        return response

    filtered = []
    for trade in response.data.closed_trades:
        closed_at = _parse_datetime(trade.closed_time)
        if closed_at is None:
            continue
        if start is not None and closed_at < start:
            continue
        if end is not None and closed_at >= end:
            continue
        filtered.append(trade)

    response.data.closed_trades = filtered
    return response


@router.post(
    "/trade/manual",
    response_model=ManualTradeResponse,
    summary="Submit manual Bybit demo trade",
    description="Places a protected Bybit demo market order using backend risk sizing.",
)
def submit_manual_trade(payload: ManualTradeRequest) -> ManualTradeResponse:
    return manual_trade_service.execute_manual_trade(payload)
