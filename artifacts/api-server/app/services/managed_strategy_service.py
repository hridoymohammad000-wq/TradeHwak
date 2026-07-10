from app.core.enums import TradingMode
from app.services.strategy_service import StrategyService


class ManagedStrategyService(StrategyService):
    """Use one liquid top-20 Bybit universe for both trading modes."""

    _TOP_VOLUME_LIMITS = {
        TradingMode.SCALPING: 20,
        TradingMode.INTRADAY: 20,
    }

    _FALLBACK_SYMBOLS = {
        TradingMode.SCALPING: [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
            "BNBUSDT",
            "XRPUSDT",
            "ADAUSDT",
            "AVAXUSDT",
            "LINKUSDT",
        ],
        TradingMode.INTRADAY: [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
            "BNBUSDT",
            "XRPUSDT",
            "ADAUSDT",
            "AVAXUSDT",
            "LINKUSDT",
        ],
    }
