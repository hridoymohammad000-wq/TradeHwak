from pydantic import BaseModel, Field

from app.schemas.common import ApiResponse


class LoginRequest(BaseModel):
    access_token: str = Field(min_length=1, max_length=512)


class AuthenticatedSession(BaseModel):
    authenticated: bool = True
    expires_at: str


class AuthenticatedSessionResponse(ApiResponse[AuthenticatedSession]):
    data: AuthenticatedSession
