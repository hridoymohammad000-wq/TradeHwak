from typing import TypedDict

from app.core.enums import Direction, Timeframe, TradingMode
from app.services.strategy_service import Candle, StrategyEvaluation, StrategyService, StrategySignal


class IntradayTrendContext(TypedDict):
    direction: Direction
    label: str
    close: float
    ema20: float
    ema50: float
    ema200: float
    rsi: float


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
    _INTRADAY_TREND_TIMEFRAME = Timeframe.H1
    _INTRADAY_SETUP_TIMEFRAME = Timeframe.M15
    _INTRADAY_ENTRY_TIMEFRAME = Timeframe.M5
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
        return self.evaluate_symbol_detailed(symbol, mode, timeframe).signal

    def evaluate_symbol_detailed(
        self,
        symbol: str,
        mode: TradingMode,
        timeframe: Timeframe | None,
    ) -> StrategyEvaluation:
        if mode == TradingMode.INTRADAY:
            return self._evaluate_intraday_pipeline(symbol)
        return self._evaluate_managed_mode(symbol, mode)

    def _evaluate_managed_mode(
        self,
        symbol: str,
        mode: TradingMode,
    ) -> StrategyEvaluation:
        setup_timeframe = self.default_timeframe(mode)
        evaluation = super().evaluate_symbol_detailed(
            symbol=symbol,
            mode=mode,
            timeframe=setup_timeframe,
        )
        signal = evaluation.signal
        if signal is None:
            return evaluation

        setup_candles = self._load_candles(
            symbol,
            self._INTERVAL_MAP[setup_timeframe],
            240,
        )
        if len(setup_candles) < 60:
            return StrategyEvaluation(
                symbol=symbol,
                outcome="insufficient_data",
                detail="Confirmation setup candles were incomplete.",
            )

        matches = self._strategy_matches(setup_candles, signal.direction)
        matched_names = [name for name, matched in matches.items() if matched]
        if not matched_names:
            return StrategyEvaluation(
                symbol=symbol,
                outcome="rejected",
                detail="No managed strategy pattern matched the setup candle structure.",
            )

        confirmation_timeframe = self._CONFIRMATION_TIMEFRAME[mode]
        confirmation = self._confirmation_context(
            symbol=symbol,
            timeframe=confirmation_timeframe,
            direction=signal.direction,
        )
        if confirmation is None:
            return StrategyEvaluation(
                symbol=symbol,
                outcome="rejected",
                detail="Closed-candle confirmation did not validate the setup.",
            )

        self._apply_confirmation_metrics(
            signal=signal,
            confirmation=confirmation,
            confirmation_timeframe=confirmation_timeframe,
            matches=matches,
            matched_names=matched_names,
        )
        return StrategyEvaluation(symbol=symbol, outcome="actionable", signal=signal)

    def _evaluate_intraday_pipeline(self, symbol: str) -> StrategyEvaluation:
        trend = self._intraday_trend_context(symbol)
        if trend is None:
            return StrategyEvaluation(
                symbol=symbol,
                outcome="rejected",
                detail="1H trend was sideways, incomplete, or not EMA/RSI aligned.",
            )

        setup_evaluation = super().evaluate_symbol_detailed(
            symbol=symbol,
            mode=TradingMode.INTRADAY,
            timeframe=self._INTRADAY_SETUP_TIMEFRAME,
        )
        signal = setup_evaluation.signal
        if signal is None:
            return setup_evaluation
        if signal.direction != trend["direction"]:
            return StrategyEvaluation(
                symbol=symbol,
                outcome="rejected",
                detail="15M setup direction did not align with the 1H trend.",
            )

        setup_candles = self._load_candles(
            symbol,
            self._INTERVAL_MAP[self._INTRADAY_SETUP_TIMEFRAME],
            240,
        )
        if len(setup_candles) < 60:
            return StrategyEvaluation(
                symbol=symbol,
                outcome="insufficient_data",
                detail="15M setup candles were incomplete.",
            )

        matches = self._strategy_matches(setup_candles, signal.direction)
        matched_names = [name for name, matched in matches.items() if matched]
        if not matched_names:
            return StrategyEvaluation(
                symbol=symbol,
                outcome="rejected",
                detail="15M setup did not match breakout, pure SMC, or hybrid rules.",
            )

        entry = self._confirmation_context(
            symbol=symbol,
            timeframe=self._INTRADAY_ENTRY_TIMEFRAME,
            direction=signal.direction,
        )
        if entry is None:
            return StrategyEvaluation(
                symbol=symbol,
                outcome="rejected",
                detail="5M entry trigger was not ready on the latest closed candle.",
            )

        signal.timeframe = self._INTRADAY_ENTRY_TIMEFRAME
        signal.entry_price = round(float(entry["close"]), 8)
        signal.current_price = signal.entry_price
        signal.metrics.update(
            {
                "trend_timeframe_minutes": 60.0,
                "trend_close": round(float(trend["close"]), 8),
                "trend_ema20": round(float(trend["ema20"]), 8),
                "trend_ema50": round(float(trend["ema50"]), 8),
                "trend_ema200": round(float(trend["ema200"]), 8),
                "trend_rsi14": round(float(trend["rsi"]), 2),
                "trend_direction": 1.0 if signal.direction == Direction.BUY else -1.0,
                "setup_timeframe_minutes": 15.0,
                "entry_timeframe_minutes": 5.0,
            }
        )
        self._apply_confirmation_metrics(
            signal=signal,
            confirmation=entry,
            confirmation_timeframe=self._INTRADAY_ENTRY_TIMEFRAME,
            matches=matches,
            matched_names=matched_names,
        )
        if entry.get("timestamp") not in (None, ""):
            signal.metrics["setup_timestamp"] = float(entry["timestamp"])
        signal.reason = (
            f"1H {str(trend['label'])} trend aligned. "
            f"15M setup matched: {', '.join(matched_names)}. "
            f"5M entry confirmed: {entry['candle_label']}, "
            f"RSI {float(entry['rsi']):.1f}, VWAP {float(entry['vwap']):.8f}."
        )
        return StrategyEvaluation(symbol=symbol, outcome="actionable", signal=signal)

    def _intraday_trend_context(
        self,
        symbol: str,
    ) -> IntradayTrendContext | None:
        candles = self._load_candles(
            symbol,
            self._INTERVAL_MAP[self._INTRADAY_TREND_TIMEFRAME],
            240,
        )
        return self._intraday_trend_context_from_candles(candles)

    @classmethod
    def _intraday_trend_context_from_candles(
        cls,
        candles: list[Candle],
    ) -> IntradayTrendContext | None:
        if len(candles) < 210:
            return None
        closes = [candle.close for candle in candles]
        close = closes[-1]
        ema20 = cls._ema(closes, 20)
        ema50 = cls._ema(closes, 50)
        ema200 = cls._ema(closes, 200)
        rsi = cls._rsi(closes, 14)
        if None in (ema20, ema50, ema200, rsi) or close <= 0:
            return None

        if close > ema20 > ema50 > ema200 and rsi >= 50.0:
            direction = Direction.BUY
            label = "bullish"
        elif close < ema20 < ema50 < ema200 and rsi <= 50.0:
            direction = Direction.SELL
            label = "bearish"
        else:
            return None

        return {
            "direction": direction,
            "label": label,
            "close": close,
            "ema20": ema20,
            "ema50": ema50,
            "ema200": ema200,
            "rsi": rsi,
        }

    def _apply_confirmation_metrics(
        self,
        *,
        signal: StrategySignal,
        confirmation: dict[str, float | bool | str | int | None],
        confirmation_timeframe: Timeframe,
        matches: dict[str, bool],
        matched_names: list[str],
    ) -> None:
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
    ) -> dict[str, float | bool | str | int | None] | None:
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
            "timestamp": latest.timestamp,
            "candle_label": candle_label,
            "candle_direction": candle_direction,
            "rsi_aligned": rsi_aligned,
            "vwap_aligned": vwap_aligned,
        }
