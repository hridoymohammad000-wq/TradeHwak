import unittest

from app.core.enums import Direction, SignalGrade, Timeframe, TradingMode
from app.services.managed_manual_trade_service import ManagedManualTradeService
from app.services.managed_strategy_service import ManagedStrategyService
from app.services.signal_registry import SignalRegistry
from app.services.strategy_service import Candle, StrategySignal


def signal(symbol: str, score: float) -> StrategySignal:
    return StrategySignal(
        symbol=symbol,
        mode=TradingMode.SCALPING,
        timeframe=Timeframe.M5,
        direction=Direction.BUY,
        grade=SignalGrade.A,
        status="actionable",
        entry_price=100.0,
        current_price=100.0,
        reason="test",
        metrics={"final_score": score},
    )


class ManagedWorkflowContractTests(unittest.TestCase):
    def test_top_twenty_universe_for_both_modes(self) -> None:
        self.assertEqual(ManagedStrategyService._TOP_VOLUME_LIMITS[TradingMode.SCALPING], 20)
        self.assertEqual(ManagedStrategyService._TOP_VOLUME_LIMITS[TradingMode.INTRADAY], 20)

    def test_mode_confirmation_timeframes(self) -> None:
        self.assertEqual(
            ManagedStrategyService._CONFIRMATION_TIMEFRAME[TradingMode.SCALPING],
            Timeframe.M1,
        )
        self.assertEqual(
            ManagedStrategyService._CONFIRMATION_TIMEFRAME[TradingMode.INTRADAY],
            Timeframe.M5,
        )

    def test_registry_ranks_and_limits_to_ten(self) -> None:
        registry = SignalRegistry()
        candidates = [signal(f"SYM{index:02d}USDT", float(index)) for index in range(15)]
        registry.replace(TradingMode.SCALPING, candidates, source="test")
        stored = registry.get(TradingMode.SCALPING)
        self.assertEqual(len(stored), 10)
        self.assertEqual([item.metrics["final_score"] for item in stored], list(map(float, range(14, 4, -1))))

    def test_breakout_requires_volume_and_level_break(self) -> None:
        history = [Candle(100, 101, 99, 100, 10) for _ in range(20)]
        bullish_breakout = history + [Candle(100, 103, 100, 102, 16)]
        weak_volume = history + [Candle(100, 103, 100, 102, 14)]
        self.assertTrue(ManagedStrategyService._breakout_match(bullish_breakout, Direction.BUY))
        self.assertFalse(ManagedStrategyService._breakout_match(weak_volume, Direction.BUY))

    def test_hybrid_requires_sweep_displacement_and_fvg(self) -> None:
        candles = [Candle(100, 101, 99, 100, 10) for _ in range(12)]
        candles.append(Candle(100, 100.5, 97, 99.5, 10))
        candles.append(Candle(99.5, 104, 102, 103.5, 20))
        self.assertTrue(ManagedStrategyService._hybrid_match(candles, Direction.BUY))

    def test_execution_position_limits(self) -> None:
        self.assertEqual(
            ManagedManualTradeService.MODE_OPEN_LIMITS[TradingMode.SCALPING],
            5,
        )
        self.assertEqual(
            ManagedManualTradeService.MODE_OPEN_LIMITS[TradingMode.INTRADAY],
            3,
        )


if __name__ == "__main__":
    unittest.main()
