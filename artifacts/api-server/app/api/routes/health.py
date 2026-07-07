from fastapi import APIRouter

from app.core.state import system_service
from app.schemas.health import HealthResponse


router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Get backend health",
    description="Returns backend availability and current foundation phase details.",
)
def get_health() -> HealthResponse:
    return system_service.get_health()
