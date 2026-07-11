from __future__ import annotations

from dataclasses import dataclass

from app.double_down.enums import ChallengeExchangeMode


@dataclass(frozen=True)
class ChallengeSafetyReport:
    code_ready: bool
    production_ready: bool
    live_mode_blocked: bool
    persistence_required: bool
    database_reachable: bool
    backup_verified: bool
    rollback_verified: bool
    demo_smoke_verified: bool
    blockers: tuple[str, ...]


def evaluate_release_safety(
    *,
    persistence_enabled: bool,
    database_reachable: bool,
    backup_verified: bool,
    rollback_verified: bool,
    demo_smoke_verified: bool,
) -> ChallengeSafetyReport:
    """Evaluate release evidence without ever enabling live-money execution.

    Code readiness means the safety contract is intact and persistence is
    configured. Production readiness additionally requires runtime evidence.
    """

    live_mode_blocked = set(ChallengeExchangeMode) == {
        ChallengeExchangeMode.PAPER,
        ChallengeExchangeMode.DEMO,
    }
    blockers: list[str] = []
    if not live_mode_blocked:
        blockers.append("LIVE_MODE_NOT_HARD_BLOCKED")
    if not persistence_enabled:
        blockers.append("PERSISTENCE_DISABLED")
    if not database_reachable:
        blockers.append("DATABASE_NOT_VERIFIED")
    if not backup_verified:
        blockers.append("BACKUP_RECOVERY_NOT_VERIFIED")
    if not rollback_verified:
        blockers.append("ROLLBACK_NOT_VERIFIED")
    if not demo_smoke_verified:
        blockers.append("DEMO_SMOKE_NOT_VERIFIED")

    code_ready = live_mode_blocked and persistence_enabled
    production_ready = code_ready and not blockers
    return ChallengeSafetyReport(
        code_ready=code_ready,
        production_ready=production_ready,
        live_mode_blocked=live_mode_blocked,
        persistence_required=True,
        database_reachable=database_reachable,
        backup_verified=backup_verified,
        rollback_verified=rollback_verified,
        demo_smoke_verified=demo_smoke_verified,
        blockers=tuple(blockers),
    )
