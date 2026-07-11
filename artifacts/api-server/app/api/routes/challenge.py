from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.state import challenge_service


router = APIRouter(prefix="/challenge", tags=["Double Down Challenge"])


class ChallengeCreateRequest(BaseModel):
    starting_balance: Decimal = Field(gt=0)
    failure_floor: Decimal = Field(gt=0)


@router.post("")
def create_challenge(payload: ChallengeCreateRequest) -> dict:
    if payload.failure_floor >= payload.starting_balance:
        raise HTTPException(status_code=422, detail="failure_floor must be below starting_balance")
    return challenge_service.create(
        starting_balance=payload.starting_balance,
        failure_floor=payload.failure_floor,
    )


@router.get("")
def list_challenges() -> list[dict]:
    return challenge_service.list()


@router.get("/{challenge_id}")
def get_challenge(challenge_id: UUID) -> dict:
    try:
        return challenge_service.get(challenge_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="challenge not found")


@router.post("/{challenge_id}/start")
def start_challenge(challenge_id: UUID) -> dict:
    return _action(challenge_id, challenge_service.start)


@router.post("/{challenge_id}/pause")
def pause_challenge(challenge_id: UUID) -> dict:
    return _action(challenge_id, challenge_service.pause)


@router.post("/{challenge_id}/resume")
def resume_challenge(challenge_id: UUID) -> dict:
    return _action(challenge_id, challenge_service.resume)


@router.post("/{challenge_id}/terminate")
def terminate_challenge(challenge_id: UUID) -> dict:
    return _action(challenge_id, challenge_service.terminate)


def _action(challenge_id: UUID, action) -> dict:
    try:
        return action(challenge_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="challenge not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
