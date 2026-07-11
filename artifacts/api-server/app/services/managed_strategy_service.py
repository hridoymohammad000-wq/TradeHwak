from app.core.enums import Direction, Timeframe, TradingMode
from app.services.strategy_service import Candle, StrategyService, StrategySignal


class ManagedStrategyService(StrategyService):
    """Top-20 liquid universe with confirmation and explicit strategy gates."""

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
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
            "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
        ],
        TradingMode.INTRADAY: [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
            "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
        ],
    }

    def evaluate_symbol(
        self,
        symbol: str,
        mode: TradingMode,
        timeframe: Timeframe | None,
    ) -> StrategySignal | None:
        setup_timeframe = self.default_timeframe(mode)
        signal = super().evaluate_symbol(
            symbol=symbol,
            mode=mode,
            timeframe=setup_timeframe,
        )
        if signal is None:
            return None

        setup_candles = self._load_candles(
            symbol,
            self._INTERVAL_MAP[setup_timeframe],
            240,
        )
        if len(setup_candles) < 60:
            return None

        matches = self._strategy_matches(setup_candles, signal.direction)
        matched_names = [name for name, matched in matches.items() if matched]
        if not matched_names:
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
                "confirmation_rsi14": round(float(confirmation["rsi"]), 2),
                "confirmation_vwap": round(float(confirmation["vwap"]), 8),
                "confirmation_close": round(float(confirmation["close"]), 8),
                "confirmation_candle_direction": float(
                    confirmation["candle_direction"]
                ),
                "confirmation_rsi_aligned": float(
                    bool(confirmation["rsi_aligned"])
                ),
                "confirmation_vwap_aligned": float(
                    bool(confirmation["vwap_aligned"])
                ),
                "strategy_breakout": float(matches["breakout"]),
                "strategy_pure_smc": float(matches["pure_smc"]),
                "strategy_hybrid": float(matches["hybrid"]),
                "strategy_match_count": float(len(matched_names)),
            }
        )
        signal.reason = (
            f"{signal.reason} Strategy match: {', '.join(matched_names)}. "
            f"Confirmed on {confirmation_timeframe.value} closed candle: "
            f"{confirmation['candle_label']}, RSI {float(confirmation['rsi']):.1f}, "
            f"VWAP {float(confirmation['vwap']):.8f}."
        )
        return signal

    def _strategy_matches(
        self,
        candles: list[Candle],
        direction: Direction,
    ) -> dict[str, bool]:
        return {
            "breakout": self._breakout_match(candles, direction),
            "pure_smc": self._pure_smc_match(candles, direction),
            "hybrid": self._hybrid_match(candles, direction),
        }

    @staticmethod
    def _breakout_match(candles: list[Candle], direction: Direction) -> bool:
        latest = candles[-1]
        lookback = candles[-21:-1]
        average_volume = sum(candle.volume for candle in lookback) / len(lookback)
        if average_volume <= 0 or latest.volume < average_volume * 1.5:
            return False

        resistance = max(candle.high for candle in lookback)
        support = min(candle.low for candle in lookback)
        if direction == Direction.BUY:
            return latest.close > resistance and latest.close > latest.open
        return latest.close < support and latest.close < latest.open

    @staticmethod
    def _has_directional_fvg(candles: list[Candle], direction: Direction) -> bool:
        for index in range(max(2, len(candles) - 8), len(candles)):
            first = candles[index - 2]
            third = candles[index]
            if direction == Direction.BUY and third.low > first.high:
                return True
            if direction == Direction.SELL and third.high < first.low:
                return True
        return False

    @classmethod
    def _pure_smc_match(cls, candles: list[Candle], direction: Direction) -> bool:
        latest = candles[-1]
        structure_window = candles[-16:-1]
        recent_window = candles[-6:-1]
        prior_high = max(candle.high for candle in structure_window)
        prior_low = min(candle.low for candle in structure_window)

        if direction == Direction.BUY:
            structure_break = latest.close > prior_high
            order_block_present = any(
                candle.close < candle.open for candle in recent_window
            )
        else:
            structure_break = latest.close < prior_low
            order_block_present = any(
                candle.close > candle.open for candle in recent_window
            )

        return (
            structure_break
            and order_block_present
            and cls._has_directional_fvg(candles, direction)
        )

    @classmethod
    def _hybrid_match(cls, candles: list[Candle], direction: Direction) -> bool:
        sweep = candles[-2]
        displacement = candles[-1]
        liquidity_window = candles[-14:-2]
        prior_high = max(candle.high for candle in liquidity_window)
        prior_low = min(candle.low for candle in liquidity_window)
        body = abs(displacement.close - displacement.open)
        average_body = sum(
            abs(candle.close - candle.open) for candle in liquidity_window
        ) / len(liquidity_window)
        # A flat/doji-only lookback has a zero average body. In that case a
        # non-zero displacement candle is still meaningful and must not be
        # rejected solely because the relative multiplier has no denominator.
        displaced = body > 0 if average_body == 0 else body >= average_body * 1.5

        if direction == Direction.BUY:
            swept_liquidity = sweep.low < prior_low and sweep.close > prior_low
            directional = displacement.close > displacement.open
        else:
            swept_liquidity = sweep.high > prior_high and sweep.close < prior_high
            directional = displacement.close < displacement.open

        return (
            swept_liquidity
            and displaced
            and directional
            and cls._has_directional_fvg(candles, direction)
        )

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
