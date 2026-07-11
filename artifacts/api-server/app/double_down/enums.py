from enum import StrEnum


class ChallengeStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    CYCLE_ACTIVE = "cycle_active"
    REPLANNING = "replanning"
    RECOVERY = "recovery"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class ChallengeSlotType(StrEnum):
    BTC_ANCHOR = "btc_anchor"
    TOP_GAINER = "top_gainer"
    TOP_LOSER = "top_loser"


class ChallengeDirection(StrEnum):
    LONG = "long"
    SHORT = "short"


class ChallengeExchangeMode(StrEnum):
    PAPER = "paper"
    DEMO = "demo"


class ChallengeTimeframe(StrEnum):
    ONE_MINUTE = "1m"


class ChallengeSlotStatus(StrEnum):
    EMPTY = "empty"
    SELECTED = "selected"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    CLOSED = "closed"


class ChallengeLedgerEntryType(StrEnum):
    DEPOSIT = "deposit"
    TRADE_PNL = "trade_pnl"
    FEE = "fee"
    ADJUSTMENT = "adjustment"
    FINAL_RECONCILIATION = "final_reconciliation"
