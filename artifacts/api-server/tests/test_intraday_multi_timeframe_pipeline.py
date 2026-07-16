import unittest
from unittest.mock import patch

from app.core.enums import Direction, SignalGrade, Timeframe, TradingMode
from app.services.managed_strategy_service import ManagedStrategyService
from app.services.strategy_service import Candle, StrategyEvaluation, StrategyService, StrategySignal


def _signal(direction: Direction = Direction.BUY) -> StrategySignal:
    return StrategySignal(
        symbol="BTCUSDT",
        mode=TradingMode.INTRADAY,
        timeframe=Timeframe.M15,
        direction=direction,
        grade=SignalGrade.A,
        status="watching",
        entry_price=100.0,
        current_price=100.0,
        reason="15M base setup",
        metrics={"final_score": 87.0, "setup_timestamp": 1.0},
    )


def _candles(direction: Direction) -> list[Candle]:
    result: list[Candle] = []
    for index in range(240):
        close = 100.0 + index if direction == Direction.BUY else 400.0 - index
        open_price = close - 0.5 if direction == Direction.BUY else close + 0.5
        result.append(
            Candle(
                open=open_price,
                high=max(open_price, close) + 0.2,
                low=min(open_price, close) - 0.2,
                close=close,
                volume=1000.0,
                timestamp=index,
            )
        )
    return result


class IntradayMultiTimeframePipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ManagedStrategyService(bybit_service=object())

    def test_intraday_timeframe_contract(self) -> None:
        self.assertEqual(self.service._INTRADAY_TREND_TIMEFRAME, Timeframe.H1)
        self.assertEqual(self.service._INTRADAY_SETUP_TIMEFRAME, Timeframe.M15)
        self.assertEqual(self.service._INTRADAY_ENTRY_TIMEFRAME, Timeframe.M5)

    def test_one_hour_trend_detects_bullish_and_bearish_bias(self) -> None:
        bullish = self.service._intraday_trend_context_from_candles(
            _candles(Direction.BUY)
        )
        bearish = self.service._intraday_trend_context_from_candles(
            _candles(Direction.SELL)
        )
        self.assertIsNotNone(bullish)
        self.assertIsNotNone(bearish)
        self.assertEqual(bullish["direction"], Direction.BUY)
        self.assertEqual(bearish["direction"], Direction.SELL)

    def test_intraday_pipeline_uses_15m_setup_and_5m_entry(self) -> None:
        signal = _signal(Direction.BUY)
        trend = {
            "direction": Direction.BUY,
            "label": "bullish",
            "close": 110.0,
            "ema20": 108.0,
            "ema50": 105.0,
            "ema200": 100.0,
            "rsi": 61.0,
        }
        entry = {
            "rsi": 58.0,
            "vwap": 104.0,
            "close": 105.0,
            "timestamp": 123456,
            "candle_label": "bullish",
            "candle_direction": 1.0,
            "rsi_aligned": True,
            "vwap_aligned": True,
        }
        setup_candles = [Candle(100, 101, 99, 100.5, 1000) for _ in range(60)]

        with (
            patch.object(
                self.service,
                "_intraday_trend_context",
                return_value=trend,
            ),
            patch.object(
                StrategyService,
                "evaluate_symbol_detailed",
                return_value=StrategyEvaluation(
                    symbol="BTCUSDT",
                    outcome="actionable",
                    signal=signal,
                ),
            ) as base_evaluation,
            patch.object(self.service, "_load_candles", return_value=setup_candles),
            patch.object(
                self.service,
                "_strategy_matches",
                return_value={"breakout": True, "pure_smc": False, "hybrid": False},
            ),
            patch.object(
                self.service,
                "_confirmation_context",
                return_value=entry,
            ) as entry_confirmation,
        ):
            result = self.service.evaluate_symbol_detailed(
                "BTCUSDT",
                TradingMode.INTRADAY,
                None,
            )

        self.assertEqual(result.outcome, "actionable")
        self.assertIsNotNone(result.signal)
        self.assertEqual(result.signal.timeframe, Timeframe.M5)
        self.assertEqual(result.signal.entry_price, 105.0)
        self.assertEqual(result.signal.metrics["trend_timeframe_minutes"], 60.0)
        self.assertEqual(result.signal.metrics["setup_timeframe_minutes"], 15.0)
        self.assertEqual(result.signal.metrics["entry_timeframe_minutes"], 5.0)
        self.assertEqual(result.signal.metrics["setup_timestamp"], 123456.0)
        self.assertIn("1H bullish trend aligned", result.signal.reason)
        base_evaluation.assert_called_once_with(
            symbol="BTCUSDT",
            mode=TradingMode.INTRADAY,
            timeframe=Timeframe.M15,
        )
        entry_confirmation.assert_called_once_with(
            symbol="BTCUSDT",
            timeframe=Timeframe.M5,
            direction=Direction.BUY,
        )

    def test_intraday_pipeline_rejects_before_setup_when_1h_bias_missing(self) -> None:
        with (
            patch.object(self.service, "_intraday_trend_context", return_value=None),
            patch.object(StrategyService, "evaluate_symbol_detailed") as base_evaluation,
        ):
            result = self.service.evaluate_symbol_detailed(
                "BTCUSDT",
                TradingMode.INTRADAY,
                None,
            )

        self.assertEqual(result.outcome, "rejected")
        self.assertIn("1H trend", result.detail)
        base_evaluation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
