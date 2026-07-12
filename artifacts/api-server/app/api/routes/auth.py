import hashlib
import hmac
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.schemas.auth import AuthenticatedSession, AuthenticatedSessionResponse, LoginRequest
from app.schemas.common import ApiResponse


router = APIRouter(prefix="/auth", tags=["Authentication"])
COOKIE_NAME = "tradehawk_session"
SESSION_TTL_SECONDS = 60 * 60 * 12


class LogoutData(BaseModel):
    logged_out: bool = True


class LogoutResponse(ApiResponse[LogoutData]):
    data: LogoutData


def _access_token() -> str:
    token = (os.environ.get("TRADEHAWK_ACCESS_TOKEN") or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TRADEHAWK_ACCESS_TOKEN is not configured.",
        )
    return token


def _sign(expiry: int, secret: str) -> str:
    payload = str(expiry)
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def _validate_session(cookie_value: str | None) -> int:
    if not cookie_value or "." not in cookie_value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    expiry_text, supplied_signature = cookie_value.split(".", 1)
    try:
        expiry = int(expiry_text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.") from exc
    expected = _sign(expiry, _access_token()).split(".", 1)[1]
    if not hmac.compare_digest(supplied_signature, expected) or expiry <= int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid.")
    return expiry


def _session_response(expiry: int, message: str) -> AuthenticatedSessionResponse:
    expires_at = datetime.fromtimestamp(expiry, tz=timezone.utc).isoformat()
    return AuthenticatedSessionResponse(
        message=message,
        data=AuthenticatedSession(expires_at=expires_at),
    )


def require_authenticated_session(
    tradehawk_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> int:
    return _validate_session(tradehawk_session)


@router.post("/login", response_model=AuthenticatedSessionResponse)
def login(payload: LoginRequest, response: Response) -> AuthenticatedSessionResponse:
    secret = _access_token()
    if not hmac.compare_digest(payload.access_token, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.")
    expiry = int(time.time()) + SESSION_TTL_SECONDS
    response.set_cookie(
        key=COOKIE_NAME,
        value=_sign(expiry, secret),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )
    return _session_response(expiry, "Login successful.")


@router.get("/session", response_model=AuthenticatedSessionResponse)
def session(expiry: int = Depends(require_authenticated_session)) -> AuthenticatedSessionResponse:
    return _session_response(expiry, "Session valid.")


@router.post("/logout", response_model=LogoutResponse)
def logout(response: Response) -> LogoutResponse:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
    )
    return LogoutResponse(message="Logout successful.", data=LogoutData())
