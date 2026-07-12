from __future__ import annotations

from typing import Any
from uuid import UUID

from app.db.repository import PersistenceRepository


class ChallengePersistence:
    """Isolated persistence gateway for Double Down challenge snapshots."""

    def __init__(self, repository: PersistenceRepository) -> None:
        self._repository = repository

    def save_snapshot(self, challenge_id: UUID, snapshot: dict[str, Any]) -> None:
        self._repository.execute_required(
            """
            INSERT INTO double_down_challenges (challenge_id, snapshot, updated_at)
            VALUES (%s, %s::jsonb, now())
            ON CONFLICT (challenge_id) DO UPDATE
            SET snapshot = EXCLUDED.snapshot, updated_at = now()
            """,
            (str(challenge_id), self._repository._json(snapshot)),
        )

    def load_snapshot(self, challenge_id: UUID) -> dict[str, Any] | None:
        row = self._repository._fetchone(
            "SELECT snapshot FROM double_down_challenges WHERE challenge_id = %s",
            (str(challenge_id),),
        )
        if not row:
            return None
        value = self._repository._json_value(row.get("snapshot"))
        return value if isinstance(value, dict) else None

    def list_snapshots(self) -> list[dict[str, Any]]:
        rows = self._repository._fetchall(
            "SELECT snapshot FROM double_down_challenges ORDER BY updated_at DESC"
        )
        snapshots: list[dict[str, Any]] = []
        for row in rows:
            value = self._repository._json_value(row.get("snapshot"))
            if isinstance(value, dict):
                snapshots.append(value)
        return snapshots
