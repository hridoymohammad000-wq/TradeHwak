from fastapi import APIRouter

from app.core.state import persistence_repository, scanner_service
from app.schemas.scanner import ScanRequest, ScanResponse


router = APIRouter(tags=["Scanner"])


@router.post(
    "/scan",
    response_model=ScanResponse,
    summary="Run scanner placeholder",
    description="Validates scan filters and returns an empty placeholder result set until a scan engine is attached.",
)
def scan_market(payload: ScanRequest | None = None) -> ScanResponse:
    response = scanner_service.scan(payload)
    persistence_repository.append_log("scan_logs", "scan_completed", response.model_dump(mode="json"))
    return response
