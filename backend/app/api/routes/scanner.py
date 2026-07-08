from fastapi import APIRouter

from app.core.state import scanner_service
from app.schemas.scanner import ScanRequest, ScanResponse


router = APIRouter(tags=["Scanner"])


@router.post(
    "/scan",
    response_model=ScanResponse,
    summary="Run scanner",
    description="Runs the existing scanner and returns actionable, rejected, skipped, and failed outcomes.",
)
def scan_market(payload: ScanRequest | None = None) -> ScanResponse:
    return scanner_service.scan(payload)
