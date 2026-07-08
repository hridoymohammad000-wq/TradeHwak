import time

from fastapi import HTTPException, status

from app.core.enums import ChartStatus, Timeframe, TradingMode
from app.schemas.chart_context import ChartCandle, ChartContextData, ChartContextResponse, IndicatorContext
from app.services.bybit_service import BybitService


class ChartContextService:
    INTERVALS = {
        Timeframe.M1: "1",
        Timeframe.M5: "5",
        Timeframe.M15: "15",
        Timeframe.H1: "60",
    }

    def __init__(self, bybit_service: BybitService) -> None:
        self._bybit_service = bybit_service

    def get_context(self, symbol: str, mode: TradingMode, timeframe: Timeframe, limit: int = 300) -> ChartContextResponse:
        normalized_symbol = symbol.strip().upper().replace("/", "")
        if not normalized_symbol:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Symbol must not be blank.")

        rows = self._bybit_service.get_closed_klines(normalized_symbol, self.INTERVALS[timeframe], limit=limit)
        candles: list[ChartCandle] = []
        for row in reversed(rows):
            try:
                candles.append(ChartCandle(
                    open_time=int(row[0]), open=float(row[1]), high=float(row[2]),
                    low=float(row[3]), close=float(row[4]), volume=float(row[5]) if row[5] not in (None, "") else None,
                    turnover=float(row[6]) if len(row) > 6 and row[6] not in (None, "") else None,
                ))
            except (TypeError, ValueError, IndexError):
                continue

        return ChartContextResponse(
            message="Real Bybit Demo chart data fetched successfully." if candles else "No chart candles were returned by Bybit Demo.",
            data=ChartContextData(
                symbol=normalized_symbol, mode=mode, timeframe=timeframe,
                chart_status=ChartStatus.CONTEXT_READY if candles else ChartStatus.PENDING_DATA,
                candles=candles, last_price=candles[-1].close if candles else None,
                indicator_context=IndicatorContext(),
                fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            ),
        )
