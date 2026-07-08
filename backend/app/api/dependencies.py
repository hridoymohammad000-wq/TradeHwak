from fastapi import HTTPException, Request, status

from app.core.config import get_app_config
from app.core.state import auth_service
from app.services.auth_service import AuthenticatedSession


def require_authenticated_session(request: Request) -> AuthenticatedSession:
    config = get_app_config()
    session_id = request.cookies.get(config.session_cookie_name)
    session = auth_service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required or session expired.",
            headers={"WWW-Authenticate": "Session"},
        )
    return session
