import hashlib
import hmac
import os
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core.config import get_app_config
from app.schemas.auth import AuthenticatedSession, AuthenticatedSessionResponse, LoginRequest
from app.schemas.common import ApiResponse


router = APIRouter(prefix="/auth", tags=["Authentication"])
COOKIE_NAME = "tradehawk_session"
SESSION_TTL_SECONDS = 60 * 60 * 12
LOGIN_ATTEMPT_WINDOW_SECONDS = 15 * 60
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
_FAILED_LOGINS: dict[str, list[float]] = {}
_LOCKED_UNTIL: dict[str, float] = {}
_LOGIN_LOCK = threading.RLock()


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


def _origin_from_url(value: str) -> str | None:
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _allowed_origins_for_request(request: Request) -> set[str]:
    config = get_app_config()
    allowed = {origin.rstrip("/") for origin in config.cors_origins if origin}
    current_origin = _origin_from_url(str(request.base_url))
    if current_origin:
        allowed.add(current_origin)
    return allowed


def _request_origin(request: Request) -> str | None:
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if not value:
            continue
        origin = _origin_from_url(value)
        if origin:
            return origin
    return None


def require_trusted_browser_origin(request: Request) -> None:
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    request_origin = _request_origin(request)
    allowed_origins = _allowed_origins_for_request(request)
    if request_origin is None or request_origin not in allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin validation failed for this mutation request.",
        )


def _client_identifier(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def _assert_login_not_rate_limited(client_id: str) -> None:
    now = time.time()
    with _LOGIN_LOCK:
        locked_until = _LOCKED_UNTIL.get(client_id, 0.0)
        if locked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Try again later.",
            )
        _LOCKED_UNTIL.pop(client_id, None)


def _record_failed_login(client_id: str) -> None:
    now = time.time()
    with _LOGIN_LOCK:
        attempts = [
            attempt
            for attempt in _FAILED_LOGINS.get(client_id, [])
            if now - attempt <= LOGIN_ATTEMPT_WINDOW_SECONDS
        ]
        attempts.append(now)
        _FAILED_LOGINS[client_id] = attempts
        if len(attempts) >= LOGIN_ATTEMPT_LIMIT:
            _LOCKED_UNTIL[client_id] = now + LOGIN_LOCKOUT_SECONDS


def _clear_failed_logins(client_id: str) -> None:
    with _LOGIN_LOCK:
        _FAILED_LOGINS.pop(client_id, None)
        _LOCKED_UNTIL.pop(client_id, None)


def require_authenticated_session(
    tradehawk_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> int:
    return _validate_session(tradehawk_session)


@router.post("/login", response_model=AuthenticatedSessionResponse)
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    _: None = Depends(require_trusted_browser_origin),
) -> AuthenticatedSessionResponse:
    secret = _access_token()
    client_id = _client_identifier(request)
    _assert_login_not_rate_limited(client_id)
    if not hmac.compare_digest(payload.access_token, secret):
        _record_failed_login(client_id)
        _assert_login_not_rate_limited(client_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.")
    _clear_failed_logins(client_id)
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
def logout(
    response: Response,
    _: None = Depends(require_trusted_browser_origin),
) -> LogoutResponse:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
    )
    return LogoutResponse(message="Logout successful.", data=LogoutData())
