from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.core.enums import ChartStatus, Timeframe, TradingMode
from app.core.trading_rules import trading_rule
from app.schemas.chart_context import (
    ChartCandle,
    ChartContextData,
    ChartContextResponse,
    IndicatorContext,
)
from app.services.bybit_service import BybitService


class ChartContextService:
    _INTERVALS = {
        Timeframe.M1: "1",
        Timeframe.M5: "5",
        Timeframe.M15: "15",
        Timeframe.H1: "60",
    }

    def __init__(self, bybit_service: BybitService) -> None:
        self._bybit_service = bybit_service

    def get_context(
        self, symbol: str, mode: TradingMode, timeframe: Timeframe | None
    ) -> ChartContextResponse:
        normalized_symbol = symbol.strip().upper().replace("/", "")
        if not normalized_symbol:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Symbol must not be blank.",
            )

        selected_timeframe = timeframe or trading_rule(mode).setup_timeframe
        interval = self._INTERVALS[selected_timeframe]
        payload = self._bybit_service._get_closed_klines(
            normalized_symbol,
            interval,
            limit=260,
        )
        rows = list(reversed(payload.get("result", {}).get("list", []) or []))

        candles: list[ChartCandle] = []
        for row in rows:
            try:
                candles.append(
                    ChartCandle(
                        open_time=int(row[0]),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]) if row[5] not in (None, "") else None,
                        turnover=float(row[6]) if len(row) > 6 and row[6] not in (None, "") else None,
                    )
                )
            except (TypeError, ValueError, IndexError):
                continue

        if not candles:
            return ChartContextResponse(
                message="No closed candles are currently available.",
                data=ChartContextData(
                    symbol=normalized_symbol,
                    mode=mode,
                    timeframe=selected_timeframe,
                    chart_status=ChartStatus.PENDING_DATA,
                    candles=[],
                    last_price=None,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                    indicator_context=IndicatorContext(),
                ),
            )

        closes = [item.close for item in candles]
        ema20_series = self._ema_series(closes, 20)
        ema50_series = self._ema_series(closes, 50)
        ema200_series = self._ema_series(closes, 200)
        macd_value, macd_signal = self._macd(closes)

        return ChartContextResponse(
            message="Chart context fetched successfully.",
            data=ChartContextData(
                symbol=normalized_symbol,
                mode=mode,
                timeframe=selected_timeframe,
                chart_status=ChartStatus.CONTEXT_READY,
                candles=candles,
                last_price=candles[-1].close,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                indicator_context=IndicatorContext(
                    ema20=self._last(ema20_series),
                    ema50=self._last(ema50_series),
                    ema200=self._last(ema200_series),
                    rsi=self._rsi(closes, 14),
                    macd=macd_value,
                    macd_signal=macd_signal,
                ),
            ),
        )

    @staticmethod
    def _ema_series(values: list[float], period: int) -> list[float]:
        if len(values) < period:
            return []
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period
        result = [ema]
        for item in values[period:]:
            ema = (item - ema) * multiplier + ema
            result.append(ema)
        return result

    @staticmethod
    def _last(values: list[float]) -> float | None:
        return round(values[-1], 8) if values else None

    @staticmethod
    def _rsi(values: list[float], period: int) -> float | None:
        if len(values) <= period:
            return None
        gains: list[float] = []
        losses: list[float] = []
        for index in range(1, len(values)):
            delta = values[index] - values[index - 1]
            gains.append(max(delta, 0.0))
            losses.append(abs(min(delta, 0.0)))
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for index in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[index]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[index]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    @classmethod
    def _macd(cls, values: list[float]) -> tuple[float | None, float | None]:
        if len(values) < 35:
            return None, None
        fast = cls._ema_aligned(values, 12)
        slow = cls._ema_aligned(values, 26)
        offset = len(fast) - len(slow)
        macd_series = [fast[index + offset] - slow[index] for index in range(len(slow))]
        signal_series = cls._ema_series(macd_series, 9)
        return (
            round(macd_series[-1], 8) if macd_series else None,
            round(signal_series[-1], 8) if signal_series else None,
        )

    @staticmethod
    def _ema_aligned(values: list[float], period: int) -> list[float]:
        if len(values) < period:
            return []
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period
        result = [ema]
        for item in values[period:]:
            ema = (item - ema) * multiplier + ema
            result.append(ema)
        return result
