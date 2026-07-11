from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from app.double_down.domain import calculate_cycle_plan
from app.double_down.strategy import StrategyDecision


@dataclass(frozen=True)
class InstrumentSizingRules:
    min_quantity: Decimal
    max_quantity: Decimal
    quantity_step: Decimal
    min_notional: Decimal = Decimal("5")
    max_notional: Decimal | None = None

    def validate(self) -> None:
        if self.min_quantity <= 0:
            raise ValueError("min_quantity must be positive")
        if self.max_quantity < self.min_quantity:
            raise ValueError("max_quantity must be >= min_quantity")
        if self.quantity_step <= 0:
            raise ValueError("quantity_step must be positive")
        if self.min_notional <= 0:
            raise ValueError("min_notional must be positive")
        if self.max_notional is not None and self.max_notional < self.min_notional:
            raise ValueError("max_notional must be >= min_notional")


@dataclass(frozen=True)
class ChallengeRiskPolicy:
    cycle_risk_pct: Decimal = Decimal("0.30")
    taker_fee_rate_per_side: Decimal = Decimal("0.00055")
    slippage_rate: Decimal = Decimal("0.00050")
    max_notional_to_balance: Decimal = Decimal("20")

    def validate(self) -> None:
        if self.cycle_risk_pct != Decimal("0.30"):
            raise ValueError("V1 cycle risk is locked at 30%")
        if self.taker_fee_rate_per_side < 0 or self.slippage_rate < 0:
            raise ValueError("fee and slippage rates cannot be negative")
        if self.max_notional_to_balance <= 0:
            raise ValueError("max_notional_to_balance must be positive")


@dataclass(frozen=True)
class PositionSizeResult:
    approved: bool
    rejection_code: str | None
    quantity: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    stop_distance: Decimal
    gross_risk: Decimal
    estimated_fees: Decimal
    estimated_slippage: Decimal
    total_estimated_loss: Decimal
    notional: Decimal
    slot_risk_budget: Decimal
    evidence: dict[str, str]


def _floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    units = (value / step).to_integral_value(rounding=ROUND_DOWN)
    return units * step


def _rejected(
    *,
    code: str,
    decision: StrategyDecision,
    slot_risk_budget: Decimal,
    evidence: dict[str, str],
) -> PositionSizeResult:
    zero = Decimal("0")
    return PositionSizeResult(
        approved=False,
        rejection_code=code,
        quantity=zero,
        entry_price=decision.entry_price or zero,
        stop_loss=decision.stop_loss or zero,
        take_profit=decision.take_profit or zero,
        stop_distance=zero,
        gross_risk=zero,
        estimated_fees=zero,
        estimated_slippage=zero,
        total_estimated_loss=zero,
        notional=zero,
        slot_risk_budget=slot_risk_budget,
        evidence=evidence,
    )


def size_challenge_position(
    *,
    current_balance: Decimal,
    approved_slots: int,
    decision: StrategyDecision,
    instrument: InstrumentSizingRules,
    policy: ChallengeRiskPolicy | None = None,
) -> PositionSizeResult:
    selected_policy = policy or ChallengeRiskPolicy()
    selected_policy.validate()
    instrument.validate()

    cycle_plan = calculate_cycle_plan(
        current_balance=current_balance,
        approved_slots=approved_slots,
        cycle_risk_pct=selected_policy.cycle_risk_pct,
    )
    slot_budget = cycle_plan.per_slot_risk

    if not decision.approved:
        return _rejected(
            code="STRATEGY_NOT_APPROVED",
            decision=decision,
            slot_risk_budget=slot_budget,
            evidence={"strategy_rejection": str(decision.rejection_code or "unknown")},
        )
    if decision.entry_price is None or decision.stop_loss is None or decision.take_profit is None:
        return _rejected(
            code="MISSING_PROTECTION_PRICES",
            decision=decision,
            slot_risk_budget=slot_budget,
            evidence={},
        )

    entry = decision.entry_price
    stop = decision.stop_loss
    take = decision.take_profit
    if min(entry, stop, take) <= 0:
        return _rejected(
            code="INVALID_PRICE",
            decision=decision,
            slot_risk_budget=slot_budget,
            evidence={},
        )

    stop_distance = abs(entry - stop)
    reward_distance = abs(take - entry)
    if stop_distance <= 0:
        return _rejected(
            code="ZERO_STOP_DISTANCE",
            decision=decision,
            slot_risk_budget=slot_budget,
            evidence={},
        )
    if reward_distance != stop_distance:
        return _rejected(
            code="RR_NOT_ONE_TO_ONE",
            decision=decision,
            slot_risk_budget=slot_budget,
            evidence={
                "risk_distance": str(stop_distance),
                "reward_distance": str(reward_distance),
            },
        )

    round_trip_fee_rate = selected_policy.taker_fee_rate_per_side * Decimal("2")
    estimated_cost_per_unit = entry * (
        round_trip_fee_rate + selected_policy.slippage_rate
    )
    loss_per_unit = stop_distance + estimated_cost_per_unit
    if loss_per_unit <= 0:
        return _rejected(
            code="INVALID_LOSS_PER_UNIT",
            decision=decision,
            slot_risk_budget=slot_budget,
            evidence={},
        )

    raw_quantity = slot_budget / loss_per_unit
    quantity = _floor_to_step(raw_quantity, instrument.quantity_step)
    if quantity < instrument.min_quantity:
        return _rejected(
            code="BELOW_MIN_QUANTITY",
            decision=decision,
            slot_risk_budget=slot_budget,
            evidence={"raw_quantity": str(raw_quantity)},
        )

    quantity = min(quantity, instrument.max_quantity)
    notional_cap = current_balance * selected_policy.max_notional_to_balance
    if instrument.max_notional is not None:
        notional_cap = min(notional_cap, instrument.max_notional)
    quantity_by_notional = _floor_to_step(notional_cap / entry, instrument.quantity_step)
    quantity = min(quantity, quantity_by_notional)

    if quantity < instrument.min_quantity:
        return _rejected(
            code="NOTIONAL_CAP_TOO_LOW",
            decision=decision,
            slot_risk_budget=slot_budget,
            evidence={"notional_cap": str(notional_cap)},
        )

    notional = quantity * entry
    if notional < instrument.min_notional:
        return _rejected(
            code="BELOW_MIN_NOTIONAL",
            decision=decision,
            slot_risk_budget=slot_budget,
            evidence={"notional": str(notional)},
        )

    gross_risk = quantity * stop_distance
    estimated_fees = notional * round_trip_fee_rate
    estimated_slippage = notional * selected_policy.slippage_rate
    total_loss = gross_risk + estimated_fees + estimated_slippage
    if total_loss > slot_budget:
        return _rejected(
            code="RISK_BUDGET_EXCEEDED",
            decision=decision,
            slot_risk_budget=slot_budget,
            evidence={"total_estimated_loss": str(total_loss)},
        )

    return PositionSizeResult(
        approved=True,
        rejection_code=None,
        quantity=quantity,
        entry_price=entry,
        stop_loss=stop,
        take_profit=take,
        stop_distance=stop_distance,
        gross_risk=gross_risk,
        estimated_fees=estimated_fees,
        estimated_slippage=estimated_slippage,
        total_estimated_loss=total_loss,
        notional=notional,
        slot_risk_budget=slot_budget,
        evidence={
            "cycle_risk_pct": str(selected_policy.cycle_risk_pct),
            "approved_slots": str(approved_slots),
            "raw_quantity": str(raw_quantity),
            "quantity_step": str(instrument.quantity_step),
            "rr_ratio": "1.0",
        },
    )
