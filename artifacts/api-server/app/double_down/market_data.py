from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from app.double_down.enums import ChallengeSlotType


@dataclass(frozen=True)
class ChallengeTicker:
    symbol: str
    price_change_pct_24h: Decimal
    turnover_24h: Decimal
    volume_24h: Decimal
    best_bid: Decimal
    best_ask: Decimal
    last_price: Decimal

    @property
    def spread_pct(self) -> Decimal:
        if self.best_bid <= 0 or self.best_ask <= 0:
            raise ValueError("bid and ask must be positive")
        if self.best_ask < self.best_bid:
            raise ValueError("best_ask cannot be below best_bid")
        return ((self.best_ask - self.best_bid) / self.best_bid) * Decimal("100")


@dataclass(frozen=True)
class ClosedCandle:
    symbol: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class MarketSelectionPolicy:
    min_turnover_24h: Decimal = Decimal("10000000")
    min_volume_24h: Decimal = Decimal("1")
    max_spread_pct: Decimal = Decimal("0.20")
    max_candle_age_seconds: int = 120


@dataclass(frozen=True)
class SelectedMarketSlot:
    slot_type: ChallengeSlotType
    symbol: str
    reason: str


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper().replace("/", "")
    if not normalized.endswith("USDT"):
        raise ValueError("challenge symbol must be a USDT market")
    return normalized


def validate_closed_one_minute_candle(
    candle: ClosedCandle,
    *,
    now: datetime | None = None,
    max_age_seconds: int = 120,
) -> None:
    if candle.close_time.tzinfo is None or candle.open_time.tzinfo is None:
        raise ValueError("candle timestamps must be timezone-aware")
    if candle.close_time <= candle.open_time:
        raise ValueError("candle close_time must be after open_time")
    duration = (candle.close_time - candle.open_time).total_seconds()
    if duration != 60:
        raise ValueError("challenge candle must be exactly one minute")
    if min(candle.open, candle.high, candle.low, candle.close) <= 0:
        raise ValueError("candle prices must be positive")
    if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
        raise ValueError("invalid OHLC range")
    if candle.volume < 0:
        raise ValueError("candle volume cannot be negative")
    reference = now or datetime.now(timezone.utc)
    if candle.close_time > reference:
        raise ValueError("open or future candle is not allowed")
    age = (reference - candle.close_time).total_seconds()
    if age > max_age_seconds:
        raise ValueError("stale candle is not allowed")


def ticker_is_eligible(ticker: ChallengeTicker, policy: MarketSelectionPolicy) -> bool:
    try:
        symbol = normalize_symbol(ticker.symbol)
        spread = ticker.spread_pct
    except ValueError:
        return False
    if symbol in {"USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "USDPUSDT"}:
        return False
    return (
        ticker.last_price > 0
        and ticker.turnover_24h >= policy.min_turnover_24h
        and ticker.volume_24h >= policy.min_volume_24h
        and spread <= policy.max_spread_pct
    )


def select_challenge_slots(
    tickers: Iterable[ChallengeTicker],
    *,
    policy: MarketSelectionPolicy | None = None,
) -> list[SelectedMarketSlot]:
    selected_policy = policy or MarketSelectionPolicy()
    eligible_by_symbol: dict[str, ChallengeTicker] = {}
    for ticker in tickers:
        if not ticker_is_eligible(ticker, selected_policy):
            continue
        symbol = normalize_symbol(ticker.symbol)
        current = eligible_by_symbol.get(symbol)
        if current is None or ticker.turnover_24h > current.turnover_24h:
            eligible_by_symbol[symbol] = ticker

    btc = eligible_by_symbol.get("BTCUSDT")
    if btc is None:
        raise ValueError("BTCUSDT must pass market eligibility filters")

    non_btc = [ticker for symbol, ticker in eligible_by_symbol.items() if symbol != "BTCUSDT"]
    gainers = sorted(
        (ticker for ticker in non_btc if ticker.price_change_pct_24h > 0),
        key=lambda item: (item.price_change_pct_24h, item.turnover_24h),
        reverse=True,
    )
    losers = sorted(
        (ticker for ticker in non_btc if ticker.price_change_pct_24h < 0),
        key=lambda item: (item.price_change_pct_24h, -item.turnover_24h),
    )

    selections = [
        SelectedMarketSlot(
            slot_type=ChallengeSlotType.BTC_ANCHOR,
            symbol="BTCUSDT",
            reason="fixed BTC anchor passed liquidity and spread filters",
        )
    ]
    used = {"BTCUSDT"}

    if gainers:
        symbol = normalize_symbol(gainers[0].symbol)
        selections.append(
            SelectedMarketSlot(
                slot_type=ChallengeSlotType.TOP_GAINER,
                symbol=symbol,
                reason="highest eligible positive 24h change",
            )
        )
        used.add(symbol)

    loser = next((item for item in losers if normalize_symbol(item.symbol) not in used), None)
    if loser is not None:
        selections.append(
            SelectedMarketSlot(
                slot_type=ChallengeSlotType.TOP_LOSER,
                symbol=normalize_symbol(loser.symbol),
                reason="lowest eligible negative 24h change",
            )
        )

    if len({item.symbol for item in selections}) != len(selections):
        raise ValueError("duplicate symbol selection is not allowed")
    return selections
