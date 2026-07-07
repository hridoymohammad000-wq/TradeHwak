from fastapi import APIRouter, Query

from app.core.state import bybit_service
from app.schemas.bybit import (
    BybitConfigStatusResponse,
    BybitConnectionStatusResponse,
    BybitMarketSnapshotResponse,
    BybitMarketTestResponse,
)


router = APIRouter(tags=["Bybit"])


@router.get(
    "/bybit/config-status",
    response_model=BybitConfigStatusResponse,
    summary="Get Bybit config status",
)
def get_config_status() -> BybitConfigStatusResponse:
    return bybit_service.get_config_status()


@router.get(
    "/bybit/connection",
    response_model=BybitConnectionStatusResponse,
    summary="Get Bybit demo connection status",
)
def get_connection_status() -> BybitConnectionStatusResponse:
    return bybit_service.get_connection_status()


@router.post(
    "/bybit/test-connection",
    response_model=BybitConnectionStatusResponse,
    summary="Test Bybit demo connection",
)
def test_connection() -> BybitConnectionStatusResponse:
    return bybit_service.get_connection_status()


@router.get(
    "/market/test",
    response_model=BybitMarketTestResponse,
    summary="Test Bybit market endpoints",
)
def get_market_test(
    symbol: str = Query(default="BTCUSDT", min_length=4, max_length=20),
) -> BybitMarketTestResponse:
    return bybit_service.get_market_test(symbol)


@router.get(
    "/market/snapshot",
    response_model=BybitMarketSnapshotResponse,
    summary="Get Bybit market snapshot",
)
def get_market_snapshot(
    symbol: str = Query(default="BTCUSDT", min_length=4, max_length=20),
) -> BybitMarketSnapshotResponse:
    return bybit_service.get_market_snapshot(symbol)
