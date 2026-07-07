from fastapi import APIRouter

from app.core.state import auto_trade_service
from app.schemas.workflow import WorkflowStatusResponse


router = APIRouter(tags=["Workflow"])


@router.get(
    "/workflow/status",
    response_model=WorkflowStatusResponse,
    summary="Get workflow control status",
    description="Returns the latest auto-trade workflow step states for the Control Center.",
)
def get_workflow_status() -> WorkflowStatusResponse:
    return auto_trade_service.get_workflow_status()
