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


class StrategyService:
    _FALLBACK_SYMBOLS: dict[TradingMode, list[str]] = {
        TradingMode.SCALPING: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"],
        TradingMode.INTRADAY: ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
    }

    _TOP_VOLUME_LIMITS: dict[TradingMode, int] = {
        TradingMode.SCALPING: 8,
        TradingMode.INTRADAY: 12,
    }

    _DEFAULT_TIMEFRAME: dict[TradingMode, Timeframe] = {
        TradingMode.SCALPING: Timeframe.M5,
        TradingMode.INTRADAY: Timeframe.M15,
    }

    _INTERVAL_MAP: dict[Timeframe, str] = {
        Timeframe.M1: "1",
        Timeframe.M5: "5",
        Timeframe.M15: "15",
        Timeframe.H1: "60",
    }

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

    def evaluate_symbol(
        self,
        symbol: str,
        mode: TradingMode,
        timeframe: Timeframe | None,
    ) -> StrategySignal | None:
        selected_timeframe = timeframe or self.default_timeframe(mode)
        interval = self._INTERVAL_MAP[selected_timeframe]
        closes = self._bybit_service.get_closed_closes(symbol, interval, limit=80)
        if len(closes) < 55:
            return None

        current_price = closes[-1]
        ema20 = self._ema(closes, 20)
        ema50 = self._ema(closes, 50)
        rsi = self._rsi(closes, 14)
        if ema20 is None or ema50 is None or rsi is None:
            return None

        trend_gap_pct = abs(ema20 - ema50) / current_price * 100 if current_price else 0
        if current_price > ema20 > ema50 and 52 <= rsi <= 72:
            direction = Direction.BUY
            grade = self._grade_signal(trend_gap_pct, rsi, bullish=True)
        elif current_price < ema20 < ema50 and 28 <= rsi <= 48:
            direction = Direction.SELL
            grade = self._grade_signal(trend_gap_pct, rsi, bullish=False)
        elif current_price > ema20 and ema20 >= ema50 * 0.999 and rsi >= 50:
            direction = Direction.BUY
            grade = SignalGrade.B_PLUS if trend_gap_pct >= 0.08 else SignalGrade.B
        elif current_price < ema20 and ema20 <= ema50 * 1.001 and rsi <= 50:
            direction = Direction.SELL
            grade = SignalGrade.B_PLUS if trend_gap_pct >= 0.08 else SignalGrade.B
        else:
            return None

        status_map = {
            SignalGrade.A_PLUS: "armed",
            SignalGrade.A: "watching",
            SignalGrade.B_PLUS: "queued",
            SignalGrade.B: "standby",
        }
        reason = self._build_reason(direction, grade, ema20, ema50, rsi, trend_gap_pct, selected_timeframe)
        return StrategySignal(
            symbol=symbol,
            mode=mode,
            timeframe=selected_timeframe,
            direction=direction,
            grade=grade,
            status=status_map[grade],
            entry_price=round(current_price, 4),
            current_price=round(current_price, 4),
            reason=reason,
        )

    @staticmethod
    def _ema(values: list[float], period: int) -> float | None:
        if len(values) < period:
            return None
        multiplier = 2 / (period + 1)
        ema_value = sum(values[:period]) / period
        for value in values[period:]:
            ema_value = (value - ema_value) * multiplier + ema_value
        return ema_value

    @staticmethod
    def _rsi(values: list[float], period: int) -> float | None:
        if len(values) <= period:
            return None
        gains: list[float] = []
        losses: list[float] = []
        for index in range(1, len(values)):
            delta = values[index] - values[index - 1]
            gains.append(max(delta, 0))
            losses.append(abs(min(delta, 0)))
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        if avg_loss == 0:
            return 100.0
        for index in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[index]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[index]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _grade_signal(trend_gap_pct: float, rsi: float, bullish: bool) -> SignalGrade:
        if bullish:
            if trend_gap_pct >= 0.35 and rsi >= 60:
                return SignalGrade.A_PLUS
            if trend_gap_pct >= 0.2 and rsi >= 56:
                return SignalGrade.A
            if trend_gap_pct >= 0.12 and rsi >= 53:
                return SignalGrade.B_PLUS
            return SignalGrade.B
        if trend_gap_pct >= 0.35 and rsi <= 40:
            return SignalGrade.A_PLUS
        if trend_gap_pct >= 0.2 and rsi <= 44:
            return SignalGrade.A
        if trend_gap_pct >= 0.12 and rsi <= 47:
            return SignalGrade.B_PLUS
        return SignalGrade.B

    @staticmethod
    def _build_reason(
        direction: Direction,
        grade: SignalGrade,
        ema20: float,
        ema50: float,
        rsi: float,
        trend_gap_pct: float,
        timeframe: Timeframe,
    ) -> str:
        bias = "bullish" if direction == Direction.BUY else "bearish"
        return (
            f"{grade.value} {bias} setup on {timeframe.value}: EMA20 "
            f"{'above' if direction == Direction.BUY else 'below'} EMA50, "
            f"trend gap {trend_gap_pct:.2f}% and RSI {rsi:.1f}."
        )
