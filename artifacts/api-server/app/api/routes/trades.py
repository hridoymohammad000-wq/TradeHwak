from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.core.state import bybit_service, manual_trade_service, trade_service
from app.schemas.trades import (
    ActiveTradesResponse,
    ClosedTradeRecord,
    ClosedTradesResponse,
    ManualTradeRequest,
    ManualTradeResponse,
)


router = APIRouter(tags=["Trades"])


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_trade_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _within_range(trade: ClosedTradeRecord, start: datetime | None, end: datetime | None) -> bool:
    closed_at = _parse_trade_time(trade.closed_time)
    if closed_at is None:
        return False
    if start is not None and closed_at < start:
        return False
    if end is not None and closed_at >= end:
        return False
    return True


def _filtered_closed_trades(start: datetime | None, end: datetime | None) -> list[ClosedTradeRecord]:
    response = trade_service.get_closed_trades()
    if start is None and end is None:
        return list(response.data.closed_trades)
    return [
        trade
        for trade in response.data.closed_trades
        if _within_range(trade, start, end)
    ]


@router.get(
    "/active-trades",
    response_model=ActiveTradesResponse,
    summary="Get active trades",
    description="Returns frontend-safe active trade sections and the closed-trade count for the requested range.",
)
def get_active_trades(
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> ActiveTradesResponse:
    trade_service.sync_with_exchange(bybit_service)
    response = trade_service.get_active_trades()
    start = _as_utc(start_time)
    end = _as_utc(end_time)
    if start is not None or end is not None:
        response.data.today_summary.closed_trades_today = len(
            _filtered_closed_trades(start, end)
        )
    return response


@router.get(
    "/closed-trades",
    response_model=ClosedTradesResponse,
    summary="Get closed trades",
    description="Returns closed trades filtered by the optional half-open UTC range [start_time, end_time).",
)
def get_closed_trades(
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> ClosedTradesResponse:
    trade_service.sync_with_exchange(bybit_service)
    start = _as_utc(start_time)
    end = _as_utc(end_time)
    response = trade_service.get_closed_trades()
    response.data.closed_trades = _filtered_closed_trades(start, end)
    return response


@router.post(
    "/trade/manual",
    response_model=ManualTradeResponse,
    summary="Submit manual Bybit demo trade",
    description="Places a protected Bybit demo market order using backend risk sizing.",
)
def submit_manual_trade(payload: ManualTradeRequest) -> ManualTradeResponse:
    return manual_trade_service.execute_manual_trade(payload)
