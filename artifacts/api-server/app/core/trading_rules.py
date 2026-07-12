from dataclasses import dataclass
from decimal import Decimal

from app.core.enums import Timeframe, TradingMode


@dataclass(frozen=True)
class ModeTradingRule:
    setup_timeframe: Timeframe
    risk_per_trade_pct: Decimal
    minimum_risk_reward: Decimal
    daily_max_net_loss_pct: Decimal
    max_trade_duration_minutes: int
    trailing_stop_enabled: bool


V2_TRADING_RULES = {
    TradingMode.SCALPING: ModeTradingRule(
        setup_timeframe=Timeframe.M1,
        risk_per_trade_pct=Decimal("0.5"),
        minimum_risk_reward=Decimal("1.5"),
        daily_max_net_loss_pct=Decimal("2"),
        max_trade_duration_minutes=59,
        trailing_stop_enabled=False,
    ),
    TradingMode.INTRADAY: ModeTradingRule(
        setup_timeframe=Timeframe.M5,
        risk_per_trade_pct=Decimal("1"),
        minimum_risk_reward=Decimal("2"),
        daily_max_net_loss_pct=Decimal("3"),
        max_trade_duration_minutes=360,
        trailing_stop_enabled=True,
    ),
}

COMBINED_DAILY_MAX_LOSS_PCT = Decimal("5")
COMBINED_MAX_OPEN_TRADES = 5


def trading_rule(mode: TradingMode) -> ModeTradingRule:
    return V2_TRADING_RULES[mode]
