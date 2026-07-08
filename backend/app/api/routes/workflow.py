from fastapi import APIRouter

from app.core.state import auto_trade_service
from app.schemas.workflow import WorkflowRunResponse, WorkflowStatusResponse


router = APIRouter(tags=["Workflow"])


@router.get(
    "/workflow/status",
    response_model=WorkflowStatusResponse,
    summary="Get workflow control status",
    description="Returns the latest auto-trade workflow step states for the Control Center.",
)
def get_workflow_status() -> WorkflowStatusResponse:
    return auto_trade_service.get_workflow_status()


@router.post(
    "/workflow/run",
    response_model=WorkflowRunResponse,
    summary="Run workflow cycle now",
    description="Triggers the current auto-trade workflow once immediately for operator verification.",
)
def run_workflow_cycle() -> WorkflowRunResponse:
    return auto_trade_service.run_cycle_now()
