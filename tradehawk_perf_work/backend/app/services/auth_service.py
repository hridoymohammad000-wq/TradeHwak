from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from threading import RLock

from app.core.config import AppConfig


@dataclass(frozen=True)
class AuthenticatedSession:
    expires_at: datetime


class AuthService:
    """Single-user opaque session manager. Raw session identifiers are never stored."""

    def __init__(self, config: AppConfig) -> None:
        self._access_token = config.access_token.get_secret_value()
        self._session_ttl = timedelta(minutes=config.session_ttl_minutes)
        self._sessions: dict[str, AuthenticatedSession] = {}
        self._lock = RLock()

    @staticmethod
    def _session_key(session_id: str) -> str:
        return sha256(session_id.encode("utf-8")).hexdigest()

    def validate_access_token(self, candidate: str | None) -> bool:
        if candidate is None:
            return False
        normalized = candidate.strip()
        if not normalized:
            return False
        return compare_digest(normalized, self._access_token)

    def create_session(self) -> tuple[str, AuthenticatedSession]:
        session_id = token_urlsafe(48)
        session = AuthenticatedSession(
            expires_at=datetime.now(timezone.utc) + self._session_ttl
        )
        with self._lock:
            self._delete_expired_locked()
            self._sessions[self._session_key(session_id)] = session
        return session_id, session

    def get_session(self, session_id: str | None) -> AuthenticatedSession | None:
        if not session_id:
            return None
        key = self._session_key(session_id)
        with self._lock:
            self._delete_expired_locked()
            return self._sessions.get(key)

    def revoke_session(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(self._session_key(session_id), None)

    def _delete_expired_locked(self) -> None:
        now = datetime.now(timezone.utc)
        expired_keys = [
            key for key, session in self._sessions.items() if session.expires_at <= now
        ]
        for key in expired_keys:
            self._sessions.pop(key, None)
