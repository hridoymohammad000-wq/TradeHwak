from dataclasses import dataclass

from app.core.enums import Direction, SignalGrade, Timeframe, TradingMode
from app.services.bybit_service import BybitService


@dataclass
class StrategySignal:
    symbol: str
    mode: TradingMode
    timeframe: Timeframe
    direction: Direction
    grade: SignalGrade
    status: str
    entry_price: float
    current_price: float
    reason: str
    metrics: dict[str, float]


@dataclass
class Candle:
    open: float
    high: float
    low: float
    close: float
    volume: float


class StrategyService:
    _FALLBACK_SYMBOLS = {
        TradingMode.SCALPING: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"],
        TradingMode.INTRADAY: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
    }
    _TOP_VOLUME_LIMITS = {TradingMode.SCALPING: 8, TradingMode.INTRADAY: 12}
    _DEFAULT_TIMEFRAME = {TradingMode.SCALPING: Timeframe.M5, TradingMode.INTRADAY: Timeframe.M15}
    _INTERVAL_MAP = {Timeframe.M1: "1", Timeframe.M5: "5", Timeframe.M15: "15", Timeframe.H1: "60"}
    _HIGHER_INTERVAL = {TradingMode.SCALPING: "60", TradingMode.INTRADAY: "240"}

    def __init__(self, bybit_service: BybitService) -> None:
        self._bybit_service = bybit_service

    def default_symbols(self, mode: TradingMode) -> list[str]:
        try:
            symbols = self._bybit_service.get_top_volume_symbols(self._TOP_VOLUME_LIMITS[mode])
            if symbols:
                return symbols
        except Exception:
            pass
        return list(self._FALLBACK_SYMBOLS[mode])

    def default_timeframe(self, mode: TradingMode) -> Timeframe:
        return self._DEFAULT_TIMEFRAME[mode]

    def evaluate_symbol(self, symbol: str, mode: TradingMode, timeframe: Timeframe | None) -> StrategySignal | None:
        selected_timeframe = timeframe or self.default_timeframe(mode)
        candles = self._load_candles(symbol, self._INTERVAL_MAP[selected_timeframe], 120)
        if len(candles) < 60:
            return None

        closes = [item.close for item in candles]
        current_price = candles[-1].close
        ema20 = self._ema(closes, 20)
        ema50 = self._ema(closes, 50)
        rsi = self._rsi(closes, 14)
        atr = self._atr(candles, 14)
        if None in (ema20, ema50, rsi, atr) or current_price <= 0:
            return None

        trend_gap_pct = abs(ema20 - ema50) / current_price * 100
        atr_pct = atr / current_price * 100
        direction = self._base_direction(current_price, ema20, ema50, rsi)
        if direction is None:
            return None

        extension_pct = abs(current_price - ema20) / current_price * 100
        maximum_extension = max(atr_pct * 2.2, 0.8 if mode == TradingMode.SCALPING else 1.25)
        if extension_pct > maximum_extension:
            return None

        base_score = self._base_score(direction, trend_gap_pct, rsi)
        higher_score = self._higher_timeframe_score(symbol, mode, direction)
        candle_score = self._candle_confirmation_score(candles, direction)
        volume_score = self._volume_confirmation_score(candles)
        extension_penalty = self._extension_penalty(extension_pct, atr_pct)
        final_score = max(0.0, min(100.0, base_score + higher_score + candle_score + volume_score - extension_penalty))
        grade = self._grade_from_score(final_score)
        if grade == SignalGrade.B and final_score < 58:
            return None

        recent = candles[-12:]
        swing_low = min(item.low for item in recent)
        swing_high = max(item.high for item in recent)
        status_map = {
            SignalGrade.A_PLUS: "armed",
            SignalGrade.A: "watching",
            SignalGrade.B_PLUS: "queued",
            SignalGrade.B: "standby",
        }
        reason = (
            f"{grade.value} {direction.value} setup on {selected_timeframe.value}: "
            f"score {final_score:.1f}, EMA gap {trend_gap_pct:.2f}%, RSI {rsi:.1f}, "
            f"HTF {higher_score:+.0f}, candle {candle_score:+.0f}, volume {volume_score:+.0f}."
        )
        return StrategySignal(
            symbol=symbol,
            mode=mode,
            timeframe=selected_timeframe,
            direction=direction,
            grade=grade,
            status=status_map[grade],
            entry_price=round(current_price, 8),
            current_price=round(current_price, 8),
            reason=reason,
            metrics={
                "current_price": round(current_price, 8),
                "ema20": round(ema20, 8),
                "ema50": round(ema50, 8),
                "rsi14": round(rsi, 2),
                "atr14": round(atr, 8),
                "atr_pct": round(atr_pct, 4),
                "swing_low": round(swing_low, 8),
                "swing_high": round(swing_high, 8),
                "trend_gap_pct": round(trend_gap_pct, 4),
                "higher_timeframe_score": round(higher_score, 2),
                "candle_score": round(candle_score, 2),
                "volume_score": round(volume_score, 2),
                "extension_penalty": round(extension_penalty, 2),
                "final_score": round(final_score, 2),
            },
        )

    def _load_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        payload = self._bybit_service._get_closed_klines(symbol, interval, limit=limit)
        rows = list(reversed(payload.get("result", {}).get("list", [])))
        result = []
        for row in rows:
            try:
                result.append(Candle(float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])))
            except (TypeError, ValueError, IndexError):
                continue
        return result

    @staticmethod
    def _base_direction(price: float, ema20: float, ema50: float, rsi: float) -> Direction | None:
        if price > ema20 > ema50 and 50 <= rsi <= 74:
            return Direction.BUY
        if price < ema20 < ema50 and 26 <= rsi <= 50:
            return Direction.SELL
        if price > ema20 and ema20 >= ema50 * 0.999 and rsi >= 49:
            return Direction.BUY
        if price < ema20 and ema20 <= ema50 * 1.001 and rsi <= 51:
            return Direction.SELL
        return None

    @staticmethod
    def _base_score(direction: Direction, trend_gap_pct: float, rsi: float) -> float:
        score = 52.0 + min(trend_gap_pct / 0.35, 1.0) * 18.0
        momentum = rsi - 50 if direction == Direction.BUY else 50 - rsi
        return score + max(0.0, min(momentum, 15.0)) * 0.8

    def _higher_timeframe_score(self, symbol: str, mode: TradingMode, direction: Direction) -> float:
        try:
            candles = self._load_candles(symbol, self._HIGHER_INTERVAL[mode], 80)
            closes = [item.close for item in candles]
            ema20 = self._ema(closes, 20)
            ema50 = self._ema(closes, 50)
            if ema20 is None or ema50 is None or not closes:
                return 0.0
            aligned = closes[-1] > ema20 > ema50 if direction == Direction.BUY else closes[-1] < ema20 < ema50
            opposed = closes[-1] < ema20 < ema50 if direction == Direction.BUY else closes[-1] > ema20 > ema50
            if aligned:
                return 10.0
            if opposed:
                return -6.0
        except Exception:
            return 0.0
        return 0.0

    @staticmethod
    def _candle_confirmation_score(candles: list[Candle], direction: Direction) -> float:
        previous, current = candles[-2], candles[-1]
        current_body = abs(current.close - current.open)
        previous_body = abs(previous.close - previous.open)
        if direction == Direction.BUY:
            engulfing = current.close > current.open and previous.close < previous.open and current.open <= previous.close and current.close >= previous.open
            directional = current.close > current.open
        else:
            engulfing = current.close < current.open and previous.close > previous.open and current.open >= previous.close and current.close <= previous.open
            directional = current.close < current.open
        if engulfing:
            return 7.0
        if directional and current_body >= previous_body * 0.7:
            return 3.0
        return 0.0

    @staticmethod
    def _volume_confirmation_score(candles: list[Candle]) -> float:
        average = sum(item.volume for item in candles[-21:-1]) / 20
        if average <= 0:
            return 0.0
        ratio = candles[-1].volume / average
        if ratio >= 1.5:
            return 6.0
        if ratio >= 1.1:
            return 3.0
        if ratio < 0.55:
            return -3.0
        return 0.0

    @staticmethod
    def _extension_penalty(extension_pct: float, atr_pct: float) -> float:
        if atr_pct <= 0:
            return 0.0
        multiple = extension_pct / atr_pct
        if multiple > 1.8:
            return 10.0
        if multiple > 1.2:
            return 5.0
        return 0.0

    @staticmethod
    def _grade_from_score(score: float) -> SignalGrade:
        if score >= 84:
            return SignalGrade.A_PLUS
        if score >= 74:
            return SignalGrade.A
        if score >= 64:
            return SignalGrade.B_PLUS
        return SignalGrade.B

    @staticmethod
    def _ema(values: list[float], period: int) -> float | None:
        if len(values) < period:
            return None
        multiplier = 2 / (period + 1)
        value = sum(values[:period]) / period
        for item in values[period:]:
            value = (item - value) * multiplier + value
        return value

    @staticmethod
    def _rsi(values: list[float], period: int) -> float | None:
        if len(values) <= period:
            return None
        gains, losses = [], []
        for index in range(1, len(values)):
            delta = values[index] - values[index - 1]
            gains.append(max(delta, 0))
            losses.append(abs(min(delta, 0)))
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for index in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[index]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[index]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _atr(candles: list[Candle], period: int) -> float | None:
        if len(candles) <= period:
            return None
        ranges = []
        for index in range(1, len(candles)):
            current = candles[index]
            previous_close = candles[index - 1].close
            ranges.append(max(current.high - current.low, abs(current.high - previous_close), abs(current.low - previous_close)))
        value = sum(ranges[:period]) / period
        for item in ranges[period:]:
            value = ((value * (period - 1)) + item) / period
        return value
