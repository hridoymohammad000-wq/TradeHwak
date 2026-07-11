from decimal import Decimal, ROUND_DOWN

from app.double_down.enums import ChallengeSlotType, ChallengeStatus
from app.double_down.schemas import ChallengeCyclePlan, ChallengeSlot


TERMINAL_STATUSES = {
    ChallengeStatus.COMPLETED,
    ChallengeStatus.FAILED,
    ChallengeStatus.TERMINATED,
}

ALLOWED_TRANSITIONS: dict[ChallengeStatus, set[ChallengeStatus]] = {
    ChallengeStatus.DRAFT: {ChallengeStatus.READY, ChallengeStatus.TERMINATED},
    ChallengeStatus.READY: {ChallengeStatus.RUNNING, ChallengeStatus.PAUSED, ChallengeStatus.TERMINATED},
    ChallengeStatus.RUNNING: {
        ChallengeStatus.CYCLE_ACTIVE,
        ChallengeStatus.PAUSED,
        ChallengeStatus.FAILED,
        ChallengeStatus.TERMINATED,
    },
    ChallengeStatus.CYCLE_ACTIVE: {
        ChallengeStatus.REPLANNING,
        ChallengeStatus.PAUSED,
        ChallengeStatus.FAILED,
        ChallengeStatus.TERMINATED,
    },
    ChallengeStatus.REPLANNING: {
        ChallengeStatus.RUNNING,
        ChallengeStatus.RECOVERY,
        ChallengeStatus.COMPLETED,
        ChallengeStatus.FAILED,
        ChallengeStatus.PAUSED,
        ChallengeStatus.TERMINATED,
    },
    ChallengeStatus.RECOVERY: {
        ChallengeStatus.CYCLE_ACTIVE,
        ChallengeStatus.RUNNING,
        ChallengeStatus.PAUSED,
        ChallengeStatus.FAILED,
        ChallengeStatus.TERMINATED,
    },
    ChallengeStatus.PAUSED: {
        ChallengeStatus.RUNNING,
        ChallengeStatus.RECOVERY,
        ChallengeStatus.FAILED,
        ChallengeStatus.TERMINATED,
    },
    ChallengeStatus.COMPLETED: set(),
    ChallengeStatus.FAILED: set(),
    ChallengeStatus.TERMINATED: set(),
}


def can_transition(current: ChallengeStatus, target: ChallengeStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def require_transition(current: ChallengeStatus, target: ChallengeStatus) -> None:
    if not can_transition(current, target):
        raise ValueError(f"invalid challenge transition: {current.value} -> {target.value}")


def calculate_cycle_plan(
    current_balance: Decimal,
    approved_slots: int,
    cycle_risk_pct: Decimal = Decimal("0.30"),
) -> ChallengeCyclePlan:
    if current_balance <= 0:
        raise ValueError("current_balance must be positive")
    if approved_slots < 1 or approved_slots > 3:
        raise ValueError("approved_slots must be between 1 and 3")
    if cycle_risk_pct != Decimal("0.30"):
        raise ValueError("V1 cycle_risk_pct is locked at 0.30")

    total_cycle_risk = (current_balance * cycle_risk_pct).quantize(
        Decimal("0.00000001"), rounding=ROUND_DOWN
    )
    per_slot_risk = (total_cycle_risk / Decimal(approved_slots)).quantize(
        Decimal("0.00000001"), rounding=ROUND_DOWN
    )
    return ChallengeCyclePlan(
        current_balance=current_balance,
        approved_slots=approved_slots,
        total_cycle_risk=total_cycle_risk,
        per_slot_risk=per_slot_risk,
    )


def validate_slot_set(slots: list[ChallengeSlot]) -> None:
    if not slots or len(slots) > 3:
        raise ValueError("slot set must contain between 1 and 3 slots")

    slot_types = [slot.slot_type for slot in slots]
    if len(slot_types) != len(set(slot_types)):
        raise ValueError("duplicate slot type is not allowed")

    selected_symbols = [slot.selected_symbol for slot in slots if slot.selected_symbol]
    if len(selected_symbols) != len(set(selected_symbols)):
        raise ValueError("duplicate selected symbol is not allowed")

    btc_slots = [slot for slot in slots if slot.slot_type == ChallengeSlotType.BTC_ANCHOR]
    if btc_slots and btc_slots[0].selected_symbol not in (None, "BTCUSDT"):
        raise ValueError("BTC anchor slot must use BTCUSDT")


def determine_replanned_status(
    *,
    current_balance: Decimal,
    starting_balance: Decimal,
    target_balance: Decimal,
    failure_floor: Decimal,
    active_trade_count: int,
) -> ChallengeStatus:
    if active_trade_count < 0 or active_trade_count > 3:
        raise ValueError("active_trade_count must be between 0 and 3")
    if current_balance <= failure_floor:
        return ChallengeStatus.FAILED
    if current_balance >= target_balance:
        return ChallengeStatus.COMPLETED if active_trade_count == 0 else ChallengeStatus.REPLANNING
    if current_balance < starting_balance:
        return ChallengeStatus.RECOVERY
    return ChallengeStatus.RUNNING
