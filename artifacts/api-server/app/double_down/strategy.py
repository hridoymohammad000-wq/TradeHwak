from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import mean

from app.double_down.enums import ChallengeDirection, ChallengeSlotType
from app.double_down.market_data import ClosedCandle, validate_closed_one_minute_candle


@dataclass(frozen=True)
class StrategyPolicy:
    minimum_candles: int = 20
    momentum_lookback: int = 5
    volume_lookback: int = 10
    minimum_body_pct: Decimal = Decimal("0.05")
    minimum_volume_ratio: Decimal = Decimal("1.20")
    minimum_confidence: Decimal = Decimal("0.60")
    stop_buffer_pct: Decimal = Decimal("0.05")


@dataclass(frozen=True)
class StrategyDecision:
    slot_type: ChallengeSlotType
    symbol: str
    approved: bool
    direction: ChallengeDirection | None
    confidence: Decimal
    strategy_name: str
    entry_price: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    rejection_code: str | None
    evidence: dict[str, str]


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00000001"))


def _reject(*, slot_type: ChallengeSlotType, symbol: str, code: str, evidence: dict[str, str]) -> StrategyDecision:
    return StrategyDecision(
        slot_type=slot_type,
        symbol=symbol,
        approved=False,
        direction=None,
        confidence=Decimal("0"),
        strategy_name="momentum_volume_v1",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        rejection_code=code,
        evidence=evidence,
    )


def evaluate_momentum_volume_strategy(
    *,
    slot_type: ChallengeSlotType,
    candles: list[ClosedCandle],
    policy: StrategyPolicy | None = None,
) -> StrategyDecision:
    selected_policy = policy or StrategyPolicy()
    if len(candles) < selected_policy.minimum_candles:
        symbol = candles[-1].symbol.upper() if candles else "UNKNOWN"
        return _reject(
            slot_type=slot_type,
            symbol=symbol,
            code="INSUFFICIENT_CANDLES",
            evidence={"received": str(len(candles)), "required": str(selected_policy.minimum_candles)},
        )

    ordered = sorted(candles, key=lambda item: item.close_time)
    symbol = ordered[-1].symbol.strip().upper()
    if any(item.symbol.strip().upper() != symbol for item in ordered):
        return _reject(slot_type=slot_type, symbol=symbol, code="MIXED_SYMBOLS", evidence={})
    if len({item.close_time for item in ordered}) != len(ordered):
        return _reject(slot_type=slot_type, symbol=symbol, code="DUPLICATE_CANDLES", evidence={})

    # Historical candles must be structurally valid; only the newest candle is
    # subject to the freshness window. Validating every historical candle against
    # the latest timestamp incorrectly classifies the lookback as stale.
    for candle in ordered:
        validate_closed_one_minute_candle(candle, now=candle.close_time)
    validate_closed_one_minute_candle(ordered[-1], now=ordered[-1].close_time)

    latest = ordered[-1]
    previous = ordered[-2]
    momentum_window = ordered[-selected_policy.momentum_lookback :]
    volume_reference = ordered[-(selected_policy.volume_lookback + 1) : -1]

    reference_close = momentum_window[0].open
    momentum_pct = ((latest.close - reference_close) / reference_close) * Decimal("100")
    body_pct = (abs(latest.close - latest.open) / latest.open) * Decimal("100")
    average_volume = Decimal(str(mean([float(item.volume) for item in volume_reference])))
    volume_ratio = latest.volume / average_volume if average_volume > 0 else Decimal("0")

    bullish_structure = latest.close > latest.open and latest.close > previous.high and momentum_pct > 0
    bearish_structure = latest.close < latest.open and latest.close < previous.low and momentum_pct < 0

    evidence = {
        "momentum_pct": str(_quantize(momentum_pct)),
        "body_pct": str(_quantize(body_pct)),
        "volume_ratio": str(_quantize(volume_ratio)),
        "previous_high": str(previous.high),
        "previous_low": str(previous.low),
        "latest_close": str(latest.close),
    }

    if body_pct < selected_policy.minimum_body_pct:
        return _reject(slot_type=slot_type, symbol=symbol, code="WEAK_CANDLE_BODY", evidence=evidence)
    if volume_ratio < selected_policy.minimum_volume_ratio:
        return _reject(slot_type=slot_type, symbol=symbol, code="LOW_VOLUME_CONFIRMATION", evidence=evidence)
    if not bullish_structure and not bearish_structure:
        return _reject(slot_type=slot_type, symbol=symbol, code="NO_DIRECTIONAL_BREAKOUT", evidence=evidence)

    direction = ChallengeDirection.LONG if bullish_structure else ChallengeDirection.SHORT
    entry = latest.close
    buffer = entry * selected_policy.stop_buffer_pct / Decimal("100")
    if direction == ChallengeDirection.LONG:
        stop = min(latest.low, previous.low) - buffer
        risk = entry - stop
        take = entry + risk
    else:
        stop = max(latest.high, previous.high) + buffer
        risk = stop - entry
        take = entry - risk

    if stop <= 0 or take <= 0 or risk <= 0:
        return _reject(slot_type=slot_type, symbol=symbol, code="INVALID_PROTECTION_PRICES", evidence=evidence)

    momentum_score = min(abs(momentum_pct) / Decimal("1.0"), Decimal("1"))
    volume_score = min(volume_ratio / Decimal("2.0"), Decimal("1"))
    body_score = min(body_pct / Decimal("0.50"), Decimal("1"))
    confidence = _quantize(
        momentum_score * Decimal("0.35")
        + volume_score * Decimal("0.35")
        + body_score * Decimal("0.30")
    )
    if confidence < selected_policy.minimum_confidence:
        return _reject(
            slot_type=slot_type,
            symbol=symbol,
            code="CONFIDENCE_BELOW_THRESHOLD",
            evidence={**evidence, "confidence": str(confidence)},
        )

    return StrategyDecision(
        slot_type=slot_type,
        symbol=symbol,
        approved=True,
        direction=direction,
        confidence=confidence,
        strategy_name="momentum_volume_v1",
        entry_price=_quantize(entry),
        stop_loss=_quantize(stop),
        take_profit=_quantize(take),
        rejection_code=None,
        evidence={**evidence, "rr_ratio": "1.0"},
    )
