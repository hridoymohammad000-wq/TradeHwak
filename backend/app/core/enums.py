from enum import Enum


class SystemMode(str, Enum):
    DEMO = "demo"


class StrategyMode(str, Enum):
    SCALPING = "scalping"
    INTRADAY = "intraday"


class Direction(str, Enum):
    BUY = "buy"
    SELL = "sell"


class SignalGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B_PLUS = "B+"
    B = "B"


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"


class SystemStatus(str, Enum):
    PENDING_INTEGRATION = "pending_integration"


class ChartStatus(str, Enum):
    PENDING_DATA = "pending_data"
    CONTEXT_READY = "context_ready"


RuntimeMode = SystemMode
TradingMode = StrategyMode
