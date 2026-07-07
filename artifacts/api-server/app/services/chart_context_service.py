from fastapi import HTTPException, status

from app.core.enums import ChartStatus, Timeframe, TradingMode
from app.schemas.chart_context import (
    ChartContextData,
    ChartContextResponse,
    IndicatorContext,
)


class ChartContextService:
    def get_context(
        self, symbol: str, mode: TradingMode, timeframe: Timeframe | None
    ) -> ChartContextResponse:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Symbol must not be blank.",
            )

        symbol_profiles: dict[str, dict[str, float]] = {
            "BTCUSDT": {
                "entry_price": 108420.0,
                "stop_loss": 108120.0,
                "take_profit": 109020.0,
                "ema20": 108332.4,
                "ema50": 108190.7,
                "ema200": 107844.2,
                "rsi": 61.8,
            },
            "ETHUSDT": {
                "entry_price": 6038.5,
                "stop_loss": 6074.0,
                "take_profit": 5964.0,
                "ema20": 6041.3,
                "ema50": 6058.8,
                "ema200": 5987.5,
                "rsi": 46.2,
            },
            "SOLUSDT": {
                "entry_price": 187.3,
                "stop_loss": 183.6,
                "take_profit": 194.7,
                "ema20": 186.8,
                "ema50": 184.9,
                "ema200": 179.4,
                "rsi": 58.1,
            },
            "XRPUSDT": {
                "entry_price": 0.9142,
                "stop_loss": 0.9228,
                "take_profit": 0.8971,
                "ema20": 0.9131,
                "ema50": 0.9165,
                "ema200": 0.9044,
                "rsi": 43.7,
            },
        }

        profile = symbol_profiles.get(normalized_symbol)
        if profile is None:
            return ChartContextResponse(
                message="Chart context fetched successfully.",
                data=ChartContextData(
                    symbol=normalized_symbol,
                    mode=mode,
                    timeframe=timeframe,
                    chart_status=ChartStatus.PENDING_DATA,
                    entry_price=None,
                    stop_loss=None,
                    take_profit=None,
                    risk_reward=None,
                    indicator_context=IndicatorContext(),
                ),
            )

        risk = abs(profile["entry_price"] - profile["stop_loss"])
        reward = abs(profile["take_profit"] - profile["entry_price"])
        risk_reward = round(reward / risk, 2) if risk else None

        return ChartContextResponse(
            message="Chart context fetched successfully.",
            data=ChartContextData(
                symbol=normalized_symbol,
                mode=mode,
                timeframe=timeframe,
                chart_status=ChartStatus.CONTEXT_READY,
                entry_price=profile["entry_price"],
                stop_loss=profile["stop_loss"],
                take_profit=profile["take_profit"],
                risk_reward=risk_reward,
                indicator_context=IndicatorContext(
                    ema20=profile["ema20"],
                    ema50=profile["ema50"],
                    ema200=profile["ema200"],
                    rsi=profile["rsi"],
                ),
            ),
        )
