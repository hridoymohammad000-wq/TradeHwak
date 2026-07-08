from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.api.dependencies import require_authenticated_session
from app.core.config import get_app_config
from app.core.state import auth_service
from app.schemas.auth import (
    LogoutResponse,
    SessionData,
    SessionResponse,
    TokenLoginRequest,
)
from app.services.auth_service import AuthenticatedSession


router = APIRouter(prefix="/auth", tags=["Authentication"])
config = get_app_config()


def _set_session_cookie(response: Response, session_id: str) -> None:
    max_age_seconds = config.session_ttl_minutes * 60
    response.set_cookie(
        key=config.session_cookie_name,
        value=session_id,
        max_age=max_age_seconds,
        path="/",
        secure=config.session_cookie_secure,
        httponly=True,
        samesite=config.session_cookie_samesite,
    )
    response.headers["Cache-Control"] = "no-store"


def _delete_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=config.session_cookie_name,
        path="/",
        secure=config.session_cookie_secure,
        httponly=True,
        samesite=config.session_cookie_samesite,
    )
    response.headers["Cache-Control"] = "no-store"


@router.post(
    "/login",
    response_model=SessionResponse,
    summary="Create private authenticated session",
)
def login(
    request: Request,
    response: Response,
    payload: TokenLoginRequest | None = None,
) -> SessionResponse:
    submitted_token = payload.access_token if payload is not None else None
    if not auth_service.validate_access_token(submitted_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Token"},
        )

    existing_session = request.cookies.get(config.session_cookie_name)
    auth_service.revoke_session(existing_session)
    session_id, session = auth_service.create_session()
    _set_session_cookie(response, session_id)
    return SessionResponse(
        message="Authenticated session created.",
        data=SessionData(authenticated=True, expires_at=session.expires_at),
    )


@router.get(
    "/session",
    response_model=SessionResponse,
    summary="Get current authenticated session",
)
def get_session(
    response: Response,
    session: AuthenticatedSession = Depends(require_authenticated_session),
) -> SessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        message="Authenticated session is valid.",
        data=SessionData(authenticated=True, expires_at=session.expires_at),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Invalidate current authenticated session",
)
def logout(request: Request, response: Response) -> LogoutResponse:
    session_id = request.cookies.get(config.session_cookie_name)
    auth_service.revoke_session(session_id)
    _delete_session_cookie(response)
    return LogoutResponse(message="Session invalidated.")
