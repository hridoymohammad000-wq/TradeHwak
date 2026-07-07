from fastapi import APIRouter

from app.core.state import settings_service
from app.schemas.mode import ModeResponse


router = APIRouter(tags=["System"])


@router.get(
    "/mode",
    response_model=ModeResponse,
    summary="Get current operating modes",
    description="Returns current system and strategy modes plus available options.",
)
def get_mode() -> ModeResponse:
    return settings_service.get_mode_summary()
