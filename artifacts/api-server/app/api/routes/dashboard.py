from fastapi import APIRouter

from app.core.state import dashboard_service
from app.schemas.dashboard import DashboardSummaryResponse


router = APIRouter(tags=["Dashboard"])


@router.get(
    "/dashboard-summary",
    response_model=DashboardSummaryResponse,
    summary="Get dashboard summary",
    description="Returns a frontend-safe operational summary for the dashboard page.",
)
def get_dashboard_summary() -> DashboardSummaryResponse:
    return dashboard_service.get_summary()
