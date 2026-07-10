from fastapi import APIRouter

from app.core.state import persistence_repository, scanner_service
from app.schemas.scanner import ScanRequest, ScanResponse


router = APIRouter(tags=["Scanner"])


@router.post(
    "/scan",
    response_model=ScanResponse,
    summary="Run scan only",
    description=(
        "Evaluates the requested market universe and updates the Signal Registry. "
        "This endpoint never submits, modifies, or closes an exchange order."
    ),
)
def scan_market(payload: ScanRequest | None = None) -> ScanResponse:
    response = scanner_service.scan(payload)
    persistence_repository.append_log(
        "scan_logs",
        "manual_scan_completed_without_execution",
        response.model_dump(mode="json"),
    )
    return response
