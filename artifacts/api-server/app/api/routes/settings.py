from fastapi import APIRouter

from app.core.state import settings_service
from app.schemas.settings import SettingsResponse, SettingsUpdate


router = APIRouter(tags=["Settings"])


@router.get(
    "/settings",
    response_model=SettingsResponse,
    summary="Get settings",
    description="Returns grouped runtime settings for frontend binding.",
)
def get_settings() -> SettingsResponse:
    return settings_service.get_settings()


@router.get(
    "/settings/view",
    response_model=SettingsResponse,
    summary="Get frontend settings view",
    description="Returns settings grouped by page sections for the settings screen.",
)
def get_settings_view() -> SettingsResponse:
    return settings_service.get_settings_view()


@router.post(
    "/settings",
    response_model=SettingsResponse,
    summary="Update settings",
    description="Applies validated in-memory settings updates and returns grouped settings.",
)
def update_settings(payload: SettingsUpdate) -> SettingsResponse:
    return settings_service.update_settings(payload)
