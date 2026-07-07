from pydantic import BaseModel

from app.schemas.common import ApiResponse


class BybitConfigStatusData(BaseModel):
    environment: str
    base_url: str
    api_key_configured: bool
    api_secret_configured: bool
    configured: bool


class BybitConfigStatusResponse(ApiResponse[BybitConfigStatusData]):
    data: BybitConfigStatusData


class BybitConnectionStatusData(BaseModel):
    code: str
    status: str
    detail: str
    equity: str | None = None
    available_balance: str | None = None
    fetched_at: str | None = None


class BybitConnectionStatusResponse(ApiResponse[BybitConnectionStatusData]):
    data: BybitConnectionStatusData


class BybitMarketServiceStatus(BaseModel):
    status: str
    code: str | None = None
    detail: str | None = None
    count: int | None = None


class BybitMarketTestData(BaseModel):
    symbol: str
    tested_at: str
    all_passed: bool
    services: dict[str, BybitMarketServiceStatus]


class BybitMarketTestResponse(ApiResponse[BybitMarketTestData]):
    data: BybitMarketTestData


class BybitMarketSnapshotData(BaseModel):
    symbol: str
    last_price: float | None = None
    mark_price: float | None = None
    index_price: float | None = None
    price_change_percent_24h: float | None = None
    volume_24h: float | None = None
    turnover_24h: float | None = None
    best_bid_price: float | None = None
    best_ask_price: float | None = None
    spread: float | None = None
    spread_percent: float | None = None
    fetched_at: str | None = None


class BybitMarketSnapshotResponse(ApiResponse[BybitMarketSnapshotData]):
    data: BybitMarketSnapshotData
