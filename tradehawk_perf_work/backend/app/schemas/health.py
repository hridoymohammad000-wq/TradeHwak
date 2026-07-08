from pydantic import BaseModel

from app.schemas.common import ApiResponse


class HealthData(BaseModel):
    status: str
    app: str
    phase: str
    execution_enabled: bool


class HealthResponse(ApiResponse[HealthData]):
    data: HealthData
