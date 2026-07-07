from fastapi import APIRouter

from app.core.state import engine_service
from app.schemas.engine import EngineControlRequest, EngineControlResponse


router = APIRouter(tags=["Engine"])


@router.post(
    "/engine/control",
    response_model=EngineControlResponse,
    summary="Update engine controls",
    description="Safely updates in-memory engine and execution control flags.",
)
def update_engine_controls(payload: EngineControlRequest) -> EngineControlResponse:
    return engine_service.update_controls(payload)
