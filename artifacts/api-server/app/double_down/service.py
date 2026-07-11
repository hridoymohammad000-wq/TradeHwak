from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.double_down.engine import ChallengeEngine
from app.double_down.enums import ChallengeStatus
from app.double_down.persistence import ChallengePersistence
from app.double_down.schemas import ChallengeConfig, ChallengeLedgerEntry, ChallengeState


class ChallengeService:
    def __init__(self, persistence: ChallengePersistence) -> None:
        self._persistence = persistence
        self._engines: dict[UUID, ChallengeEngine] = {}

    def create(self, *, starting_balance: Decimal, failure_floor: Decimal) -> dict:
        engine = ChallengeEngine.create(
            starting_balance=starting_balance,
            failure_floor=failure_floor,
        )
        engine.mark_ready()
        self._engines[engine.config.challenge_id] = engine
        return self._save(engine)

    def get(self, challenge_id: UUID) -> dict:
        return self._get_engine(challenge_id).snapshot()

    def list(self) -> list[dict]:
        snapshots = [engine.snapshot() for engine in self._engines.values()]
        persisted = self._persistence.list_snapshots()
        seen = {item["config"]["challenge_id"] for item in snapshots}
        snapshots.extend(
            item for item in persisted
            if item.get("config", {}).get("challenge_id") not in seen
        )
        return snapshots

    def start(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        engine.start()
        return self._save(engine)

    def pause(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        engine.pause()
        return self._save(engine)

    def resume(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        engine.resume()
        return self._save(engine)

    def terminate(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        engine.terminate()
        return self._save(engine)

    def _save(self, engine: ChallengeEngine) -> dict:
        snapshot = engine.snapshot()
        self._persistence.save_snapshot(engine.config.challenge_id, snapshot)
        return snapshot

    def _get_engine(self, challenge_id: UUID) -> ChallengeEngine:
        existing = self._engines.get(challenge_id)
        if existing is not None:
            return existing
        snapshot = self._persistence.load_snapshot(challenge_id)
        if snapshot is None:
            raise KeyError(str(challenge_id))
        engine = ChallengeEngine(
            config=ChallengeConfig.model_validate(snapshot["config"]),
            state=ChallengeState.model_validate(snapshot["state"]),
            ledger=[ChallengeLedgerEntry.model_validate(row) for row in snapshot.get("ledger", [])],
        )
        engine.validate_isolation()
        if engine.state.status == ChallengeStatus.CYCLE_ACTIVE:
            engine.state.status = ChallengeStatus.PAUSED
        self._engines[challenge_id] = engine
        return engine
