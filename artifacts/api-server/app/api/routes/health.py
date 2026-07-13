from fastapi import APIRouter, Response, status

from app.core.state import system_service
from app.schemas.health import HealthResponse


router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Get backend health",
    description="Returns backend availability and current foundation phase details.",
)
def get_health(response: Response) -> HealthResponse:
    health = system_service.get_health()
    if health.data.status != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return health
