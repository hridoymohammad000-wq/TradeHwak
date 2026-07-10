import logging
import time
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP

from fastapi import HTTPException

from app.core.enums import Direction
from app.services.bybit_service import BybitService
from app.services.trade_service import TradeService


logger = logging.getLogger(__name__)


class TrailingStopService:
    """Tighten Bybit Demo stop losses only in the profitable direction.

    LONG stops can only move upward. SHORT stops can only move downward.
    The original stop distance is retained as the trailing distance, so the
    stop never loosens when price retraces.
    """

    def __init__(self, bybit_service: BybitService, trade_service: TradeService) -> None:
        self._bybit_service = bybit_service
        self._trade_service = trade_service
        self._last_submitted: dict[str, float] = {}

    def manage_open_trades(self) -> dict[str, int]:
        response = self._trade_service.get_active_trades().data
        trades = [*response.scalping_trades, *response.intraday_trades]
        updated = 0
        skipped = 0
        failed = 0

        for trade in trades:
            if not self._has_valid_prices(
                trade.entry_price,
                trade.current_price,
                trade.stop_loss,
            ):
                skipped += 1
                continue

            try:
                original_risk = self._original_risk_distance(trade)
                new_stop = self._candidate_stop(
                    direction=trade.direction,
                    entry_price=Decimal(str(trade.entry_price)),
                    current_price=Decimal(str(trade.current_price)),
                    old_stop=Decimal(str(trade.stop_loss)),
                    original_risk=original_risk,
                )
            except (InvalidOperation, ValueError):
                skipped += 1
                continue

            if new_stop is None:
                skipped += 1
                continue

            try:
                instrument = self._bybit_service.get_validated_symbol(trade.symbol)["instrument"]
                tick = Decimal(
                    str(instrument.get("priceFilter", {}).get("tickSize") or "0")
                )
                rounded_stop = self._round_stop(new_stop, tick, trade.direction)
                if not self._strictly_improves(
                    trade.direction,
                    Decimal(str(trade.stop_loss)),
                    rounded_stop,
                ):
                    skipped += 1
                    continue

                submitted = self._last_submitted.get(trade.symbol)
                if submitted is not None and abs(submitted - float(rounded_stop)) < 1e-12:
                    skipped += 1
                    continue

                payload = {
                    "category": "linear",
                    "symbol": trade.symbol,
                    "tpslMode": "Full",
                    "positionIdx": 0,
                    "stopLoss": self._format_decimal(rounded_stop, tick),
                    "slTriggerBy": "MarkPrice",
                }
                self._submit_with_retry(payload)
                self._last_submitted[trade.symbol] = float(rounded_stop)
                updated += 1
            except HTTPException as exc:
                failed += 1
                logger.warning("Trailing stop update failed for %s: %s", trade.symbol, exc.detail)
            except Exception:
                failed += 1
                logger.exception("Unexpected trailing stop error for %s", trade.symbol)

        return {"updated": updated, "skipped": skipped, "failed": failed}

    @staticmethod
    def _original_risk_distance(trade) -> Decimal:
        try:
            planned_risk = Decimal(str(trade.planned_risk_usdt))
            qty = Decimal(str(trade.qty))
            if planned_risk > 0 and qty > 0:
                return planned_risk / qty
        except (InvalidOperation, TypeError, ValueError):
            pass
        return abs(Decimal(str(trade.entry_price)) - Decimal(str(trade.stop_loss)))

    @staticmethod
    def _candidate_stop(
        *,
        direction: Direction,
        entry_price: Decimal,
        current_price: Decimal,
        old_stop: Decimal,
        original_risk: Decimal,
    ) -> Decimal | None:
        if entry_price <= 0 or current_price <= 0 or old_stop <= 0 or original_risk <= 0:
            return None

        if direction == Direction.BUY:
            if current_price <= entry_price:
                return None
            candidate = current_price - original_risk
            return candidate if candidate > old_stop else None

        if current_price >= entry_price:
            return None
        candidate = current_price + original_risk
        return candidate if candidate < old_stop else None

    @staticmethod
    def _strictly_improves(
        direction: Direction,
        old_stop: Decimal,
        new_stop: Decimal,
    ) -> bool:
        return new_stop > old_stop if direction == Direction.BUY else new_stop < old_stop

    @staticmethod
    def _round_stop(value: Decimal, tick: Decimal, direction: Direction) -> Decimal:
        if tick <= 0:
            return value
        rounding = ROUND_DOWN if direction == Direction.BUY else ROUND_UP
        return ((value / tick).to_integral_value(rounding=rounding) * tick).normalize()

    @staticmethod
    def _format_decimal(value: Decimal, tick: Decimal) -> str:
        normalized = tick.normalize()
        decimals = abs(normalized.as_tuple().exponent) if normalized.as_tuple().exponent < 0 else 0
        return f"{value:.{decimals}f}"

    @staticmethod
    def _has_valid_prices(entry_price, current_price, stop_loss) -> bool:
        return all(value not in (None, 0, 0.0, "") for value in (entry_price, current_price, stop_loss))

    def _submit_with_retry(self, payload: dict) -> None:
        last_error: HTTPException | None = None
        for attempt in range(2):
            try:
                self._bybit_service._private_post("/v5/position/trading-stop", payload)
                return
            except HTTPException as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.25)
        if last_error is not None:
            raise last_error
