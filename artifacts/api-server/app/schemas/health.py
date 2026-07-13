from pydantic import BaseModel

from app.schemas.common import ApiResponse


class HealthData(BaseModel):
    status: str
    app: str
    phase: str
    execution_enabled: bool
    persistence_ready: bool | None = None
    bybit_ready: bool | None = None
    workers_ready: bool | None = None
    worker_status: dict[str, dict[str, bool | str | int | None]] = {}
    block_reason: str | None = None


class HealthResponse(ApiResponse[HealthData]):
    data: HealthData
