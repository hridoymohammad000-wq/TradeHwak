from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ApiResponse


class TokenLoginRequest(BaseModel):
    access_token: str | None = None


class SessionData(BaseModel):
    authenticated: bool
    expires_at: datetime


class SessionResponse(ApiResponse[SessionData]):
    data: SessionData


class LogoutResponse(ApiResponse[None]):
    data: None = None
