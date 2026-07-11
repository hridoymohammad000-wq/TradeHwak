from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.double_down.domain import calculate_cycle_plan, determine_replanned_status, require_transition
from app.double_down.enums import ChallengeLedgerEntryType, ChallengeStatus
from app.double_down.schemas import (
    ChallengeConfig,
    ChallengeCyclePlan,
    ChallengeLedgerEntry,
    ChallengeState,
)


@dataclass
class ChallengeEngine:
    """Deterministic, isolated Phase 3 core engine.

    This engine owns only challenge configuration, state, cycle planning, and
    ledger arithmetic. It has no access to TradeHawk balances, exchange clients,
    credentials, market data, or order execution.
    """

    config: ChallengeConfig
    state: ChallengeState
    ledger: list[ChallengeLedgerEntry] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        starting_balance: Decimal,
        failure_floor: Decimal,
        challenge_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> "ChallengeEngine":
        now = created_at or datetime.now(timezone.utc)
        resolved_id = challenge_id or uuid4()
        config = ChallengeConfig(
            challenge_id=resolved_id,
            starting_balance=starting_balance,
            target_balance=starting_balance * Decimal("2"),
            failure_floor=failure_floor,
            created_at=now,
        )
        state = ChallengeState(
            challenge_id=resolved_id,
            status=ChallengeStatus.DRAFT,
            current_balance=starting_balance,
            recovery_target=starting_balance,
        )
        deposit = ChallengeLedgerEntry(
            entry_id=uuid4(),
            challenge_id=resolved_id,
            cycle_number=0,
            entry_type=ChallengeLedgerEntryType.DEPOSIT,
            balance_before=Decimal("0"),
            amount=starting_balance,
            balance_after=starting_balance,
            reference_id="initial_challenge_balance",
            created_at=now,
        )
        return cls(config=config, state=state, ledger=[deposit])

    def mark_ready(self) -> None:
        self._transition(ChallengeStatus.READY)

    def start(self) -> None:
        self._transition(ChallengeStatus.RUNNING)

    def pause(self) -> None:
        self._transition(ChallengeStatus.PAUSED)

    def resume(self) -> None:
        target = (
            ChallengeStatus.RECOVERY
            if self.state.current_balance < self.config.starting_balance
            else ChallengeStatus.RUNNING
        )
        self._transition(target)

    def terminate(self) -> None:
        self._transition(ChallengeStatus.TERMINATED)

    def plan_cycle(self, approved_slots: int) -> ChallengeCyclePlan:
        if self.state.status not in {ChallengeStatus.RUNNING, ChallengeStatus.RECOVERY}:
            raise ValueError("cycle planning requires running or recovery status")
        if self.state.active_trade_count != 0:
            raise ValueError("cannot plan a new cycle while challenge trades are active")
        return calculate_cycle_plan(
            current_balance=self.state.current_balance,
            approved_slots=approved_slots,
            cycle_risk_pct=self.config.cycle_risk_pct,
        )

    def activate_cycle(self, active_trade_count: int) -> None:
        if active_trade_count < 1 or active_trade_count > self.config.max_active_trades:
            raise ValueError("active_trade_count must be between 1 and 3")
        self._transition(ChallengeStatus.CYCLE_ACTIVE)
        self.state.cycle_number += 1
        self.state.active_trade_count = active_trade_count

    def close_cycle(
        self,
        *,
        net_pnl: Decimal,
        fees: Decimal = Decimal("0"),
        reference_id: str | None = None,
        closed_at: datetime | None = None,
    ) -> ChallengeStatus:
        if self.state.status != ChallengeStatus.CYCLE_ACTIVE:
            raise ValueError("only an active cycle can be closed")
        if fees < 0:
            raise ValueError("fees cannot be negative")

        self._transition(ChallengeStatus.REPLANNING)
        before = self.state.current_balance
        net_change = net_pnl - fees
        after = before + net_change
        if after < 0:
            raise ValueError("challenge balance cannot become negative")

        now = closed_at or datetime.now(timezone.utc)
        self.ledger.append(
            ChallengeLedgerEntry(
                entry_id=uuid4(),
                challenge_id=self.config.challenge_id,
                cycle_number=self.state.cycle_number,
                entry_type=ChallengeLedgerEntryType.TRADE_PNL,
                balance_before=before,
                amount=net_change,
                balance_after=after,
                reference_id=reference_id,
                created_at=now,
            )
        )
        self.state.current_balance = after
        self.state.active_trade_count = 0
        self.state.last_replanned_at = now
        self.state.recovery_target = self.config.starting_balance

        target = determine_replanned_status(
            current_balance=after,
            starting_balance=self.config.starting_balance,
            target_balance=self.config.target_balance,
            failure_floor=self.config.failure_floor,
            active_trade_count=0,
        )
        self._transition(target)
        if target == ChallengeStatus.COMPLETED:
            self.state.completed_at = now
        elif target == ChallengeStatus.FAILED:
            self.state.failed_at = now
        return target

    def ledger_balance(self) -> Decimal:
        if not self.ledger:
            return Decimal("0")
        return self.ledger[-1].balance_after

    def validate_isolation(self) -> None:
        if self.state.challenge_id != self.config.challenge_id:
            raise ValueError("challenge state/config identity mismatch")
        for entry in self.ledger:
            if entry.challenge_id != self.config.challenge_id:
                raise ValueError("foreign ledger entry detected")
        if self.ledger_balance() != self.state.current_balance:
            raise ValueError("challenge ledger and state balance mismatch")

    def snapshot(self) -> dict:
        self.validate_isolation()
        return {
            "config": self.config.model_dump(mode="json"),
            "state": self.state.model_dump(mode="json"),
            "ledger": [entry.model_dump(mode="json") for entry in self.ledger],
        }

    def _transition(self, target: ChallengeStatus) -> None:
        require_transition(self.state.status, target)
        self.state.status = target
