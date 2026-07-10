from __future__ import annotations

from dataclasses import dataclass

from app.services.profit_tracking_service import ProfitTrackingState


@dataclass(frozen=True)
class RiskGuardDecision:
    allowed: bool
    configured_risk_budget: float
    approved_risk_budget: float
    available_lock_cushion: float | None
    active_planned_risk: float
    locked_floor_pct: float
    reason: str | None = None


class RiskExecutionGuard:
    """Keep worst-case new execution risk above the locked daily profit floor."""

    def evaluate(
        self,
        *,
        configured_risk_budget: float,
        profit_state: ProfitTrackingState,
        active_planned_risk: float,
    ) -> RiskGuardDecision:
        configured = max(float(configured_risk_budget), 0.0)
        active_risk = max(float(active_planned_risk), 0.0)
        locked_floor = max(float(profit_state.daily_locked_floor_pct), 0.0)

        if configured <= 0:
            return RiskGuardDecision(
                allowed=False,
                configured_risk_budget=configured,
                approved_risk_budget=0.0,
                available_lock_cushion=None,
                active_planned_risk=active_risk,
                locked_floor_pct=locked_floor,
                reason="Configured risk budget is zero.",
            )

        # Before a profit floor exists, normal configured risk rules remain active.
        if locked_floor <= 0:
            return RiskGuardDecision(
                allowed=True,
                configured_risk_budget=configured,
                approved_risk_budget=configured,
                available_lock_cushion=None,
                active_planned_risk=active_risk,
                locked_floor_pct=0.0,
            )

        baseline = profit_state.daily_start_equity
        if baseline is None or baseline <= 0:
            return RiskGuardDecision(
                allowed=False,
                configured_risk_budget=configured,
                approved_risk_budget=0.0,
                available_lock_cushion=0.0,
                active_planned_risk=active_risk,
                locked_floor_pct=locked_floor,
                reason="Locked-profit baseline equity is unavailable.",
            )

        cushion_pct = max(
            float(profit_state.daily_realized_pct) - locked_floor,
            0.0,
        )
        gross_cushion = float(baseline) * cushion_pct / 100.0
        available_cushion = max(gross_cushion - active_risk, 0.0)
        approved = min(configured, available_cushion)

        if approved <= 0:
            return RiskGuardDecision(
                allowed=False,
                configured_risk_budget=configured,
                approved_risk_budget=0.0,
                available_lock_cushion=available_cushion,
                active_planned_risk=active_risk,
                locked_floor_pct=locked_floor,
                reason=(
                    f"Daily locked floor {locked_floor:.2f}% leaves no new risk capacity "
                    "after existing open-trade risk."
                ),
            )

        return RiskGuardDecision(
            allowed=True,
            configured_risk_budget=configured,
            approved_risk_budget=approved,
            available_lock_cushion=available_cushion,
            active_planned_risk=active_risk,
            locked_floor_pct=locked_floor,
            reason=(
                "Risk budget reduced to protect the daily locked floor."
                if approved < configured
                else None
            ),
        )
