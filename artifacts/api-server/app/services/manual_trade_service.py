import logging
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP

from fastapi import HTTPException, status

from app.core.enums import Direction, Timeframe, TradingMode
from app.db.repository import PersistenceRepository
from app.schemas.trades import ManualTradeData, ManualTradeRequest, ManualTradeResponse
from app.services.bybit_service import BybitService
from app.services.settings_service import SettingsService
from app.services.trade_service import TradeService

logger = logging.getLogger(__name__)


class ManualTradeService:
    def __init__(self, settings_service: SettingsService, bybit_service: BybitService, trade_service: TradeService, repository: PersistenceRepository | None = None) -> None:
        self._settings_service = settings_service
        self._bybit_service = bybit_service
        self._trade_service = trade_service
        self._repository = repository

    def execute_manual_trade(self, payload: ManualTradeRequest, signal_id: str | None = None) -> ManualTradeResponse:
        settings_state = self._settings_service.get_settings_state()
        if settings_state.system_mode != "demo":
            raise HTTPException(status_code=400, detail="Manual execution is locked to demo mode.")
        if settings_state.emergency_stop:
            raise HTTPException(status_code=400, detail="Release emergency stop before sending orders.")
        if settings_state.risk_per_trade_pct <= 0:
            raise HTTPException(status_code=400, detail="Set risk per trade above 0%.")

        connection = self._bybit_service.get_connection_status().data
        if connection.code != "CONNECTED":
            raise HTTPException(status_code=400, detail=f"Bybit Demo is not ready: {connection.detail}")

        symbol_meta = self._bybit_service.get_validated_symbol(payload.symbol)
        symbol = symbol_meta["symbol"]
        ticker = self._bybit_service.get_raw_ticker(symbol)
        wallet = self._bybit_service.get_wallet_snapshot()
        market_price = self._positive_decimal(
            ticker.get("result", {}).get("list", [{}])[0].get("markPrice")
            or ticker.get("result", {}).get("list", [{}])[0].get("lastPrice"),
            "Market price is unavailable.",
        )

        stop_loss, take_profit = self._resolve_protection_prices(
            symbol=symbol,
            direction=payload.direction,
            mode=payload.mode,
            timeframe=payload.timeframe,
            market_price=market_price,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
        )
        constraints = self._instrument_constraints(symbol_meta["instrument"])
        rounded_stop = self._rounded_protection_price(stop_loss, constraints["tickSize"], payload.direction, "SL")
        rounded_take = self._rounded_protection_price(take_profit, constraints["tickSize"], payload.direction, "TP")
        self._validate_price_order(payload.direction, market_price, rounded_stop, rounded_take)

        risk_distance = abs(market_price - rounded_stop)
        available_balance = Decimal(str(wallet["available"]))
        if available_balance <= 0 or risk_distance <= 0:
            raise HTTPException(status_code=400, detail="Balance or risk distance is invalid.")

        risk_budget = available_balance * Decimal(str(settings_state.risk_per_trade_pct)) / Decimal("100")
        qty = self._round_to_step(risk_budget / risk_distance, constraints["qtyStep"], ROUND_DOWN)
        if qty <= 0 or qty < constraints["minQty"]:
            raise HTTPException(status_code=400, detail=f"Calculated quantity {qty} is below Bybit minimum {constraints['minQty']}.")
        if constraints["maxQty"] > 0 and qty > constraints["maxQty"]:
            qty = self._round_to_step(constraints["maxQty"], constraints["qtyStep"], ROUND_DOWN)

        notional = qty * market_price
        if constraints["minNotional"] > 0 and notional < constraints["minNotional"]:
            raise HTTPException(status_code=400, detail=f"Order value {notional} is below Bybit minimum {constraints['minNotional']}.")

        planned_risk = qty * risk_distance
        if planned_risk > risk_budget:
            raise HTTPException(status_code=400, detail="Planned risk exceeds configured risk budget.")
        risk_reward = self._risk_reward(payload.direction, market_price, rounded_stop, rounded_take)
        if risk_reward < Decimal("2"):
            raise HTTPException(status_code=400, detail=f"Risk-reward {risk_reward:.2f} is below 2.00.")

        side = "Buy" if payload.direction == Direction.BUY else "Sell"
        qty_string = self._format_decimal(qty, constraints["qtyStep"])
        order_payload = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": qty_string,
            "timeInForce": "IOC",
            "positionIdx": 0,
            "stopLoss": self._format_decimal(rounded_stop, constraints["tickSize"]),
            "takeProfit": self._format_decimal(rounded_take, constraints["tickSize"]),
            "slTriggerBy": "MarkPrice",
            "tpTriggerBy": "MarkPrice",
        }
        try:
            order = self._bybit_service.create_private_order(order_payload)
        except HTTPException as exc:
            self._log(
                "order_rejected",
                {
                    "symbol": symbol,
                    "side": side,
                    "qty": qty_string,
                    "market_price": float(market_price),
                    "stop_loss": float(rounded_stop),
                    "take_profit": float(rounded_take),
                    "planned_risk_usdt": float(planned_risk),
                    "detail": exc.detail,
                },
            )
            raise

        order_id = order.get("result", {}).get("orderId")
        if not order_id:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Bybit returned no orderId.")

        response = ManualTradeResponse(
            message="Bybit demo trade submitted successfully.",
            data=ManualTradeData(
                status="submitted",
                order_id=order_id,
                symbol=symbol,
                side=side,
                qty=qty_string,
                market_price=float(market_price),
                stop_loss=float(rounded_stop),
                take_profit=float(rounded_take),
                risk_reward=float(risk_reward),
                notional=float(notional),
            ),
        )
        self._trade_service.register_open_trade(
            symbol=symbol,
            mode=payload.mode,
            direction=payload.direction,
            entry_price=float(market_price),
            stop_loss=float(rounded_stop),
            take_profit=float(rounded_take),
            timeframe=payload.timeframe,
            notional=float(notional),
            planned_risk_usdt=float(planned_risk),
            risk_reward=float(risk_reward),
            signal_id=signal_id,
            order_id=order_id,
            qty=qty_string,
        )
        self._log(
            "order_submitted",
            {
                **response.model_dump(mode="json"),
                "signal_id": signal_id,
                "risk_budget_usdt": float(risk_budget),
            },
        )
        return response

    def execute_strategy_trade(self, *, symbol: str, direction: Direction, mode: TradingMode, timeframe: Timeframe | None, signal_id: str | None = None) -> ManualTradeResponse:
        return self.execute_manual_trade(ManualTradeRequest(symbol=symbol, direction=direction, mode=mode, timeframe=timeframe), signal_id=signal_id)

    def _resolve_protection_prices(self, *, symbol: str, direction: Direction, mode: TradingMode, timeframe: Timeframe | None, market_price: Decimal, stop_loss: float | None, take_profit: float | None) -> tuple[Decimal, Decimal]:
        if (stop_loss is None) != (take_profit is None):
            raise HTTPException(status_code=400, detail="Provide both stop loss and take profit, or leave both empty.")
        if stop_loss is not None and take_profit is not None:
            return self._positive_decimal(stop_loss, "Stop loss is invalid."), self._positive_decimal(take_profit, "Take profit is invalid.")

        interval_map = {Timeframe.M1: "1", Timeframe.M5: "5", Timeframe.M15: "15", Timeframe.H1: "60"}
        interval = interval_map.get(timeframe, "5" if mode == TradingMode.SCALPING else "15")
        try:
            candles = self._load_ohlc(symbol, interval, 80)
            atr = self._atr(candles, 14)
            if atr is None or len(candles) < 20:
                raise ValueError("insufficient ATR candles")
            recent = candles[-12:]
            swing_low = min(item[2] for item in recent)
            swing_high = max(item[1] for item in recent)
            atr_buffer = atr * Decimal("0.35")
            minimum_distance = max(market_price * Decimal("0.0035"), atr * Decimal("0.80"))
            maximum_distance = market_price * (Decimal("0.025") if mode == TradingMode.SCALPING else Decimal("0.040"))
            structural_stop = swing_low - atr_buffer if direction == Direction.BUY else swing_high + atr_buffer
            distance = market_price - structural_stop if direction == Direction.BUY else structural_stop - market_price
            distance = max(minimum_distance, min(distance, maximum_distance))
            generated_sl = market_price - distance if direction == Direction.BUY else market_price + distance
            generated_tp = market_price + distance * Decimal("2") if direction == Direction.BUY else market_price - distance * Decimal("2")
            self._log(
                "protection_generated",
                {
                    "symbol": symbol,
                    "interval": interval,
                    "atr": float(atr),
                    "swing": float(swing_low if direction == Direction.BUY else swing_high),
                    "stop_loss": float(generated_sl),
                    "take_profit": float(generated_tp),
                },
            )
            return generated_sl, generated_tp
        except Exception as exc:
            fallback_pct = Decimal("0.0065") if mode == TradingMode.SCALPING else Decimal("0.0100")
            logger.warning("ATR swing fallback for %s: %s", symbol, exc)
            if direction == Direction.BUY:
                return market_price * (Decimal("1") - fallback_pct), market_price * (Decimal("1") + fallback_pct * Decimal("2"))
            return market_price * (Decimal("1") + fallback_pct), market_price * (Decimal("1") - fallback_pct * Decimal("2"))

    def _load_ohlc(self, symbol: str, interval: str, limit: int) -> list[tuple[Decimal, Decimal, Decimal, Decimal]]:
        payload = self._bybit_service._get_closed_klines(symbol, interval, limit=limit)
        rows = list(reversed(payload.get("result", {}).get("list", [])))
        result = []
        for row in rows:
            try:
                result.append((Decimal(str(row[1])), Decimal(str(row[2])), Decimal(str(row[3])), Decimal(str(row[4]))))
            except (InvalidOperation, TypeError, ValueError, IndexError):
                continue
        return result

    @staticmethod
    def _atr(candles: list[tuple[Decimal, Decimal, Decimal, Decimal]], period: int) -> Decimal | None:
        if len(candles) <= period:
            return None
        ranges = []
        for index in range(1, len(candles)):
            _, high, low, _ = candles[index]
            previous_close = candles[index - 1][3]
            ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        value = sum(ranges[:period], Decimal("0")) / Decimal(period)
        for item in ranges[period:]:
            value = ((value * Decimal(period - 1)) + item) / Decimal(period)
        return value

    def _log(self, event_type: str, payload: dict) -> None:
        if self._repository is not None:
            self._repository.append_log("execution_logs", event_type, payload)

    @staticmethod
    def _positive_decimal(value, message: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=message) from exc
        if result <= 0:
            raise HTTPException(status_code=400, detail=message)
        return result

    @staticmethod
    def _instrument_constraints(instrument: dict) -> dict[str, Decimal]:
        lot = instrument.get("lotSizeFilter", {})
        price = instrument.get("priceFilter", {})
        return {
            "tickSize": Decimal(str(price.get("tickSize") or "0")),
            "qtyStep": Decimal(str(lot.get("qtyStep") or "0")),
            "minQty": Decimal(str(lot.get("minOrderQty") or "0")),
            "maxQty": Decimal(str(lot.get("maxMktOrderQty") or lot.get("maxOrderQty") or "0")),
            "minNotional": Decimal(str(lot.get("minNotionalValue") or "0")),
        }

    @staticmethod
    def _round_to_step(value: Decimal, step: Decimal, rounding: str) -> Decimal:
        if step <= 0:
            return value
        return ((value / step).to_integral_value(rounding=rounding) * step).normalize()

    @staticmethod
    def _format_decimal(value: Decimal, step: Decimal) -> str:
        decimals = abs(step.normalize().as_tuple().exponent) if step.normalize().as_tuple().exponent < 0 else 0
        return f"{value:.{decimals}f}"

    @staticmethod
    def _rounded_protection_price(value: Decimal, tick: Decimal, direction: Direction, purpose: str) -> Decimal:
        rounding = ROUND_UP if (direction == Direction.BUY and purpose == "SL") or (direction == Direction.SELL and purpose == "TP") else ROUND_DOWN
        return ManualTradeService._round_to_step(value, tick, rounding)

    @staticmethod
    def _validate_price_order(direction: Direction, market: Decimal, stop: Decimal, take: Decimal) -> None:
        valid = stop < market < take if direction == Direction.BUY else take < market < stop
        if not valid:
            raise HTTPException(status_code=400, detail="Invalid SL/TP price order.")

    @staticmethod
    def _risk_reward(direction: Direction, market: Decimal, stop: Decimal, take: Decimal) -> Decimal:
        risk = market - stop if direction == Direction.BUY else stop - market
        reward = take - market if direction == Direction.BUY else market - take
        return reward / risk if risk > 0 else Decimal("0")
