from __future__ import annotations

from decimal import Decimal
from copy import deepcopy
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
        snapshot = self._save(engine)
        self._engines[engine.config.challenge_id] = engine
        return snapshot

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
        previous = self._snapshot_copy(engine)
        engine.start()
        return self._save_with_rollback(engine, previous)

    def pause(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        previous = self._snapshot_copy(engine)
        engine.pause()
        return self._save_with_rollback(engine, previous)

    def resume(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        previous = self._snapshot_copy(engine)
        engine.resume()
        return self._save_with_rollback(engine, previous)

    def terminate(self, challenge_id: UUID) -> dict:
        engine = self._get_engine(challenge_id)
        previous = self._snapshot_copy(engine)
        engine.terminate()
        return self._save_with_rollback(engine, previous)

    def _save(self, engine: ChallengeEngine) -> dict:
        snapshot = engine.snapshot()
        self._persistence.save_snapshot(engine.config.challenge_id, snapshot)
        return snapshot

    def _save_with_rollback(
        self,
        engine: ChallengeEngine,
        previous_snapshot: dict,
    ) -> dict:
        try:
            return self._save(engine)
        except Exception:
            restored = self._engine_from_snapshot(previous_snapshot)
            self._engines[engine.config.challenge_id] = restored
            raise

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

    @staticmethod
    def _snapshot_copy(engine: ChallengeEngine) -> dict:
        return deepcopy(engine.snapshot())

    @staticmethod
    def _engine_from_snapshot(snapshot: dict) -> ChallengeEngine:
        return ChallengeEngine(
            config=ChallengeConfig.model_validate(snapshot["config"]),
            state=ChallengeState.model_validate(snapshot["state"]),
            ledger=[
                ChallengeLedgerEntry.model_validate(row)
                for row in snapshot.get("ledger", [])
            ],
        )
