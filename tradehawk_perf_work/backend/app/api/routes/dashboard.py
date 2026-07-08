from datetime import datetime

from fastapi import APIRouter, Query

from app.core.state import dashboard_service
from app.schemas.dashboard import DashboardSummaryResponse


router = APIRouter(tags=["Dashboard"])


@router.get(
    "/dashboard-summary",
    response_model=DashboardSummaryResponse,
    summary="Get dashboard summary",
    description="Returns real persisted trade and Bybit Demo account summary data.",
)
def get_dashboard_summary(
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
) -> DashboardSummaryResponse:
    return dashboard_service.get_summary(start_time=start_time, end_time=end_time)
