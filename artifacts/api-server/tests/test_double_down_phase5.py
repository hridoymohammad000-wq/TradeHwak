import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.double_down.enums import ChallengeDirection, ChallengeSlotType
from app.double_down.market_data import ClosedCandle
from app.double_down.strategy import StrategyPolicy, evaluate_momentum_volume_strategy


class DoubleDownPhase5StrategyTests(unittest.TestCase):
    def make_candles(self, *, bullish: bool, latest_volume: Decimal = Decimal("250")) -> list[ClosedCandle]:
        start = datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc)
        candles = []
        price = Decimal("100")
        for index in range(19):
            open_price = price
            close_price = price + (Decimal("0.05") if bullish else Decimal("-0.05"))
            high = max(open_price, close_price) + Decimal("0.05")
            low = min(open_price, close_price) - Decimal("0.05")
            candles.append(
                ClosedCandle(
                    symbol="BTCUSDT",
                    open_time=start + timedelta(minutes=index),
                    close_time=start + timedelta(minutes=index + 1),
                    open=open_price,
                    high=high,
                    low=low,
                    close=close_price,
                    volume=Decimal("100"),
                )
            )
            price = close_price

        previous = candles[-1]
        latest_open = previous.close
        if bullish:
            latest_close = previous.high + Decimal("0.50")
            latest_high = latest_close + Decimal("0.10")
            latest_low = latest_open - Decimal("0.10")
        else:
            latest_close = previous.low - Decimal("0.50")
            latest_high = latest_open + Decimal("0.10")
            latest_low = latest_close - Decimal("0.10")
        candles.append(
            ClosedCandle(
                symbol="BTCUSDT",
                open_time=start + timedelta(minutes=19),
                close_time=start + timedelta(minutes=20),
                open=latest_open,
                high=latest_high,
                low=latest_low,
                close=latest_close,
                volume=latest_volume,
            )
        )
        return candles

    def test_bullish_breakout_returns_long_with_exact_one_to_one_rr(self):
        decision = evaluate_momentum_volume_strategy(
            slot_type=ChallengeSlotType.BTC_ANCHOR,
            candles=self.make_candles(bullish=True),
        )
        self.assertTrue(decision.approved)
        self.assertEqual(decision.direction, ChallengeDirection.LONG)
        self.assertLess(decision.stop_loss, decision.entry_price)
        self.assertGreater(decision.take_profit, decision.entry_price)
        self.assertEqual(
            decision.entry_price - decision.stop_loss,
            decision.take_profit - decision.entry_price,
        )

    def test_bearish_breakout_returns_short_with_exact_one_to_one_rr(self):
        decision = evaluate_momentum_volume_strategy(
            slot_type=ChallengeSlotType.TOP_LOSER,
            candles=self.make_candles(bullish=False),
        )
        self.assertTrue(decision.approved)
        self.assertEqual(decision.direction, ChallengeDirection.SHORT)
        self.assertGreater(decision.stop_loss, decision.entry_price)
        self.assertLess(decision.take_profit, decision.entry_price)
        self.assertEqual(
            decision.stop_loss - decision.entry_price,
            decision.entry_price - decision.take_profit,
        )

    def test_low_volume_is_rejected_with_evidence(self):
        decision = evaluate_momentum_volume_strategy(
            slot_type=ChallengeSlotType.TOP_GAINER,
            candles=self.make_candles(bullish=True, latest_volume=Decimal("50")),
        )
        self.assertFalse(decision.approved)
        self.assertEqual(decision.rejection_code, "LOW_VOLUME_CONFIRMATION")
        self.assertIn("volume_ratio", decision.evidence)

    def test_insufficient_candles_are_rejected(self):
        decision = evaluate_momentum_volume_strategy(
            slot_type=ChallengeSlotType.BTC_ANCHOR,
            candles=self.make_candles(bullish=True)[:10],
        )
        self.assertFalse(decision.approved)
        self.assertEqual(decision.rejection_code, "INSUFFICIENT_CANDLES")

    def test_mixed_symbols_are_rejected(self):
        candles = self.make_candles(bullish=True)
        candles[-1] = ClosedCandle(
            symbol="ETHUSDT",
            open_time=candles[-1].open_time,
            close_time=candles[-1].close_time,
            open=candles[-1].open,
            high=candles[-1].high,
            low=candles[-1].low,
            close=candles[-1].close,
            volume=candles[-1].volume,
        )
        decision = evaluate_momentum_volume_strategy(
            slot_type=ChallengeSlotType.TOP_GAINER,
            candles=candles,
        )
        self.assertFalse(decision.approved)
        self.assertEqual(decision.rejection_code, "MIXED_SYMBOLS")

    def test_confidence_threshold_can_fail_closed(self):
        policy = StrategyPolicy(minimum_confidence=Decimal("0.99"))
        decision = evaluate_momentum_volume_strategy(
            slot_type=ChallengeSlotType.BTC_ANCHOR,
            candles=self.make_candles(bullish=True),
            policy=policy,
        )
        self.assertFalse(decision.approved)
        self.assertEqual(decision.rejection_code, "CONFIDENCE_BELOW_THRESHOLD")


if __name__ == "__main__":
    unittest.main()
