from app.core.enums import Direction, Timeframe, TradingMode
from app.services.strategy_service import StrategyService, StrategySignal


class ManagedStrategyService(StrategyService):
    """Top-20 liquid universe with mandatory lower-timeframe confirmation."""

    _TOP_VOLUME_LIMITS = {
        TradingMode.SCALPING: 20,
        TradingMode.INTRADAY: 20,
    }
    _CONFIRMATION_TIMEFRAME = {
        TradingMode.SCALPING: Timeframe.M1,
        TradingMode.INTRADAY: Timeframe.M5,
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

    def evaluate_symbol(
        self,
        symbol: str,
        mode: TradingMode,
        timeframe: Timeframe | None,
    ) -> StrategySignal | None:
        # Signal setups are deliberately locked to the agreed mode timeframe:
        # scalping = 5m setup, intraday = 15m setup.
        setup_timeframe = self.default_timeframe(mode)
        signal = super().evaluate_symbol(
            symbol=symbol,
            mode=mode,
            timeframe=setup_timeframe,
        )
        if signal is None:
            return None

        confirmation_timeframe = self._CONFIRMATION_TIMEFRAME[mode]
        confirmation = self._confirmation_context(
            symbol=symbol,
            timeframe=confirmation_timeframe,
            direction=signal.direction,
        )
        if confirmation is None:
            return None

        signal.metrics.update(
            {
                "confirmation_timeframe_minutes": float(
                    self._INTERVAL_MAP[confirmation_timeframe]
                ),
                "confirmation_rsi14": round(confirmation["rsi"], 2),
                "confirmation_vwap": round(confirmation["vwap"], 8),
                "confirmation_close": round(confirmation["close"], 8),
                "confirmation_candle_direction": confirmation["candle_direction"],
                "confirmation_rsi_aligned": confirmation["rsi_aligned"],
                "confirmation_vwap_aligned": confirmation["vwap_aligned"],
            }
        )
        signal.reason = (
            f"{signal.reason} Confirmed on {confirmation_timeframe.value} closed candle: "
            f"{confirmation['candle_label']}, RSI {confirmation['rsi']:.1f}, "
            f"VWAP {confirmation['vwap']:.8f}."
        )
        return signal

    def _confirmation_context(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        direction: Direction,
    ) -> dict[str, float | bool | str] | None:
        candles = self._load_candles(
            symbol,
            self._INTERVAL_MAP[timeframe],
            60,
        )
        if len(candles) < 30:
            return None

        latest = candles[-1]
        closes = [candle.close for candle in candles]
        rsi = self._rsi(closes, 14)
        if rsi is None:
            return None

        vwap_window = candles[-20:]
        total_volume = sum(candle.volume for candle in vwap_window)
        if total_volume <= 0:
            return None
        vwap = sum(
            ((candle.high + candle.low + candle.close) / 3.0) * candle.volume
            for candle in vwap_window
        ) / total_volume

        if direction == Direction.BUY:
            candle_aligned = latest.close > latest.open
            rsi_aligned = 50.0 <= rsi <= 75.0
            vwap_aligned = latest.close > vwap
            candle_label = "bullish"
            candle_direction = 1.0
        else:
            candle_aligned = latest.close < latest.open
            rsi_aligned = 25.0 <= rsi <= 50.0
            vwap_aligned = latest.close < vwap
            candle_label = "bearish"
            candle_direction = -1.0

        # A signal needs a directional closed candle plus at least one momentum
        # confirmation: RSI alignment OR VWAP alignment.
        if not candle_aligned or not (rsi_aligned or vwap_aligned):
            return None

        return {
            "rsi": rsi,
            "vwap": vwap,
            "close": latest.close,
            "candle_label": candle_label,
            "candle_direction": candle_direction,
            "rsi_aligned": rsi_aligned,
            "vwap_aligned": vwap_aligned,
        }
