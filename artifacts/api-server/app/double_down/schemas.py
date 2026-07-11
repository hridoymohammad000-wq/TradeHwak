from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.double_down.enums import (
    ChallengeDirection,
    ChallengeExchangeMode,
    ChallengeLedgerEntryType,
    ChallengeSlotStatus,
    ChallengeSlotType,
    ChallengeStatus,
    ChallengeTimeframe,
)


class ChallengeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    challenge_id: UUID
    starting_balance: Decimal = Field(gt=0)
    target_balance: Decimal = Field(gt=0)
    failure_floor: Decimal = Field(gt=0)
    cycle_risk_pct: Decimal = Field(default=Decimal("0.30"), gt=0, le=Decimal("0.30"))
    max_active_trades: int = Field(default=3, ge=1, le=3)
    timeframe: ChallengeTimeframe = ChallengeTimeframe.ONE_MINUTE
    rr_ratio: Decimal = Field(default=Decimal("1.0"), gt=0)
    exchange_mode: ChallengeExchangeMode = ChallengeExchangeMode.PAPER
    created_at: datetime

    @model_validator(mode="after")
    def validate_locked_v1_rules(self) -> "ChallengeConfig":
        expected_target = self.starting_balance * Decimal("2")
        if self.target_balance != expected_target:
            raise ValueError("target_balance must equal starting_balance × 2")
        if self.failure_floor >= self.starting_balance:
            raise ValueError("failure_floor must be below starting_balance")
        if self.cycle_risk_pct != Decimal("0.30"):
            raise ValueError("V1 cycle_risk_pct is locked at 0.30")
        if self.max_active_trades != 3:
            raise ValueError("V1 max_active_trades is locked at 3")
        if self.rr_ratio != Decimal("1.0"):
            raise ValueError("V1 rr_ratio is locked at 1.0")
        return self


class ChallengeState(BaseModel):
    challenge_id: UUID
    status: ChallengeStatus = ChallengeStatus.DRAFT
    current_balance: Decimal = Field(gt=0)
    recovery_target: Decimal = Field(gt=0)
    cycle_number: int = Field(default=0, ge=0)
    active_trade_count: int = Field(default=0, ge=0, le=3)
    last_replanned_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None


class ChallengeSlot(BaseModel):
    slot_type: ChallengeSlotType
    selected_symbol: str | None = None
    direction: ChallengeDirection | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    strategy_name: str | None = None
    rejection_reason: str | None = None
    approved_risk: Decimal = Field(default=Decimal("0"), ge=0)
    status: ChallengeSlotStatus = ChallengeSlotStatus.EMPTY

    @model_validator(mode="after")
    def validate_slot(self) -> "ChallengeSlot":
        if self.selected_symbol is not None:
            normalized = self.selected_symbol.strip().upper()
            if not normalized.endswith("USDT"):
                raise ValueError("selected_symbol must be a USDT symbol")
            self.selected_symbol = normalized
        if self.slot_type == ChallengeSlotType.BTC_ANCHOR and self.selected_symbol not in (None, "BTCUSDT"):
            raise ValueError("BTC anchor slot must use BTCUSDT")
        if self.status in {ChallengeSlotStatus.APPROVED, ChallengeSlotStatus.ACTIVE}:
            if not self.selected_symbol or self.direction is None or self.approved_risk <= 0:
                raise ValueError("approved or active slots require symbol, direction, and positive approved_risk")
        return self


class ChallengeTrade(BaseModel):
    challenge_trade_id: UUID
    challenge_id: UUID
    cycle_number: int = Field(ge=1)
    slot_type: ChallengeSlotType
    symbol: str
    direction: ChallengeDirection
    entry_price: Decimal = Field(gt=0)
    stop_loss: Decimal = Field(gt=0)
    take_profit: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    planned_risk: Decimal = Field(gt=0)
    gross_pnl: Decimal | None = None
    fees: Decimal = Field(default=Decimal("0"), ge=0)
    net_pnl: Decimal | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    close_reason: str | None = None

    @model_validator(mode="after")
    def validate_prices_and_result(self) -> "ChallengeTrade":
        self.symbol = self.symbol.strip().upper()
        if self.direction == ChallengeDirection.LONG:
            if not self.stop_loss < self.entry_price < self.take_profit:
                raise ValueError("LONG trade requires stop_loss < entry_price < take_profit")
        else:
            if not self.take_profit < self.entry_price < self.stop_loss:
                raise ValueError("SHORT trade requires take_profit < entry_price < stop_loss")
        if self.closed_at is not None and self.net_pnl is None:
            raise ValueError("closed trade requires net_pnl")
        return self


class ChallengeLedgerEntry(BaseModel):
    entry_id: UUID
    challenge_id: UUID
    cycle_number: int = Field(ge=0)
    entry_type: ChallengeLedgerEntryType
    balance_before: Decimal = Field(ge=0)
    amount: Decimal
    balance_after: Decimal = Field(ge=0)
    reference_id: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def validate_balance_math(self) -> "ChallengeLedgerEntry":
        if self.balance_before + self.amount != self.balance_after:
            raise ValueError("balance_after must equal balance_before + amount")
        return self


class ChallengeCyclePlan(BaseModel):
    current_balance: Decimal = Field(gt=0)
    approved_slots: int = Field(ge=1, le=3)
    total_cycle_risk: Decimal = Field(gt=0)
    per_slot_risk: Decimal = Field(gt=0)
