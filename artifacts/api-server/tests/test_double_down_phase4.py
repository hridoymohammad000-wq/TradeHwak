import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.double_down.enums import ChallengeSlotType
from app.double_down.market_data import (
    ChallengeTicker,
    ClosedCandle,
    MarketSelectionPolicy,
    select_challenge_slots,
    ticker_is_eligible,
    validate_closed_one_minute_candle,
)


NOW = datetime(2026, 7, 11, 9, 0, tzinfo=timezone.utc)


def ticker(symbol, change, turnover="20000000", volume="1000", bid="100", ask="100.05", last="100"):
    return ChallengeTicker(
        symbol=symbol,
        price_change_pct_24h=Decimal(change),
        turnover_24h=Decimal(turnover),
        volume_24h=Decimal(volume),
        best_bid=Decimal(bid),
        best_ask=Decimal(ask),
        last_price=Decimal(last),
    )


class DoubleDownPhase4MarketTests(unittest.TestCase):
    def test_valid_closed_one_minute_candle(self):
        candle = ClosedCandle(
            symbol="BTCUSDT",
            open_time=NOW - timedelta(minutes=1),
            close_time=NOW,
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=Decimal("25"),
        )
        validate_closed_one_minute_candle(candle, now=NOW)

    def test_future_and_stale_candles_are_rejected(self):
        future = ClosedCandle(
            symbol="BTCUSDT",
            open_time=NOW,
            close_time=NOW + timedelta(minutes=1),
            open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"), volume=Decimal("1"),
        )
        with self.assertRaises(ValueError):
            validate_closed_one_minute_candle(future, now=NOW)

        stale = ClosedCandle(
            symbol="BTCUSDT",
            open_time=NOW - timedelta(minutes=4),
            close_time=NOW - timedelta(minutes=3),
            open=Decimal("100"), high=Decimal("101"), low=Decimal("99"), close=Decimal("100"), volume=Decimal("1"),
        )
        with self.assertRaises(ValueError):
            validate_closed_one_minute_candle(stale, now=NOW, max_age_seconds=120)

    def test_liquidity_and_spread_filters(self):
        policy = MarketSelectionPolicy()
        self.assertTrue(ticker_is_eligible(ticker("BTCUSDT", "1"), policy))
        self.assertFalse(ticker_is_eligible(ticker("ETHUSDT", "2", turnover="1000"), policy))
        self.assertFalse(ticker_is_eligible(ticker("SOLUSDT", "2", bid="100", ask="101"), policy))
        self.assertFalse(ticker_is_eligible(ticker("USDCUSDT", "0.1"), policy))

    def test_selects_btc_top_gainer_and_top_loser(self):
        selections = select_challenge_slots([
            ticker("BTCUSDT", "1"),
            ticker("ETHUSDT", "4"),
            ticker("SOLUSDT", "8"),
            ticker("XRPUSDT", "-3"),
            ticker("ADAUSDT", "-7"),
        ])
        self.assertEqual(
            [(item.slot_type, item.symbol) for item in selections],
            [
                (ChallengeSlotType.BTC_ANCHOR, "BTCUSDT"),
                (ChallengeSlotType.TOP_GAINER, "SOLUSDT"),
                (ChallengeSlotType.TOP_LOSER, "ADAUSDT"),
            ],
        )

    def test_ineligible_extreme_mover_is_not_selected(self):
        selections = select_challenge_slots([
            ticker("BTCUSDT", "1"),
            ticker("DOGEUSDT", "50", turnover="100"),
            ticker("ETHUSDT", "5"),
            ticker("XRPUSDT", "-2"),
        ])
        self.assertEqual(selections[1].symbol, "ETHUSDT")

    def test_duplicate_ticker_rows_collapse_by_symbol(self):
        selections = select_challenge_slots([
            ticker("BTCUSDT", "1"),
            ticker("ETHUSDT", "3", turnover="20000000"),
            ticker("eth/usdt", "6", turnover="30000000"),
            ticker("SOLUSDT", "-4"),
        ])
        symbols = [item.symbol for item in selections]
        self.assertEqual(symbols.count("ETHUSDT"), 1)
        self.assertEqual(len(symbols), len(set(symbols)))

    def test_missing_eligible_btc_fails_closed(self):
        with self.assertRaises(ValueError):
            select_challenge_slots([
                ticker("ETHUSDT", "5"),
                ticker("SOLUSDT", "-5"),
            ])


if __name__ == "__main__":
    unittest.main()
