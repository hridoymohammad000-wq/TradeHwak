from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse
from app.core.state import challenge_service


router = APIRouter(prefix="/challenge", tags=["Double Down Challenge"])


class ChallengeCreateRequest(BaseModel):
    starting_balance: Decimal = Field(gt=0)
    failure_floor: Decimal = Field(gt=0)


@router.post("")
def create_challenge(payload: ChallengeCreateRequest) -> ApiResponse[dict]:
    if payload.failure_floor >= payload.starting_balance:
        raise HTTPException(status_code=422, detail="failure_floor must be below starting_balance")
    try:
        snapshot = challenge_service.create(
            starting_balance=payload.starting_balance,
            failure_floor=payload.failure_floor,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return ApiResponse(message="Challenge created successfully.", data=snapshot)


@router.get("")
def list_challenges() -> ApiResponse[list[dict]]:
    try:
        snapshots = challenge_service.list()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return ApiResponse(message="Challenges fetched successfully.", data=snapshots)


@router.get("/{challenge_id}")
def get_challenge(challenge_id: UUID) -> ApiResponse[dict]:
    try:
        snapshot = challenge_service.get(challenge_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="challenge not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return ApiResponse(message="Challenge fetched successfully.", data=snapshot)


@router.post("/{challenge_id}/start")
def start_challenge(challenge_id: UUID) -> ApiResponse[dict]:
    return _action(challenge_id, challenge_service.start, "Challenge started successfully.")


@router.post("/{challenge_id}/pause")
def pause_challenge(challenge_id: UUID) -> ApiResponse[dict]:
    return _action(challenge_id, challenge_service.pause, "Challenge paused successfully.")


@router.post("/{challenge_id}/resume")
def resume_challenge(challenge_id: UUID) -> ApiResponse[dict]:
    return _action(challenge_id, challenge_service.resume, "Challenge resumed successfully.")


@router.post("/{challenge_id}/terminate")
def terminate_challenge(challenge_id: UUID) -> ApiResponse[dict]:
    return _action(challenge_id, challenge_service.terminate, "Challenge terminated successfully.")


@router.post("/{challenge_id}/run-cycle")
def run_challenge_cycle(challenge_id: UUID) -> ApiResponse[dict]:
    return _action(challenge_id, challenge_service.run_cycle, "Challenge cycle executed successfully.")


@router.post("/{challenge_id}/finalize-cycle")
def finalize_challenge_cycle(challenge_id: UUID) -> ApiResponse[dict]:
    return _action(challenge_id, challenge_service.finalize_cycle, "Challenge cycle finalized successfully.")


def _action(challenge_id: UUID, action, message: str) -> ApiResponse[dict]:
    try:
        snapshot = action(challenge_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="challenge not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return ApiResponse(message=message, data=snapshot)
