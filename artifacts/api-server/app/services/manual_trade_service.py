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
    def __init__(
        self,
        settings_service: SettingsService,
        bybit_service: BybitService,
        trade_service: TradeService,
        repository: PersistenceRepository | None = None,
    ) -> None:
        self._settings_service = settings_service
        self._bybit_service = bybit_service
        self._trade_service = trade_service
        self._repository = repository

    def execute_manual_trade(
        self,
        payload: ManualTradeRequest,
        signal_id: str | None = None,
    ) -> ManualTradeResponse:
        settings_state = self._settings_service.get_settings_state()
        if settings_state.system_mode != "demo":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Manual execution is locked to demo mode in the current build.",
            )
        if settings_state.emergency_stop:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Release emergency stop before sending manual orders.",
            )
        if settings_state.risk_per_trade_pct <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Set risk per trade above 0% before sending manual orders.",
            )

        connection = self._bybit_service.get_connection_status().data
        if connection.code != "CONNECTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bybit Demo is not ready: {connection.detail}",
            )

        symbol_meta = self._bybit_service.get_validated_symbol(payload.symbol)
        ticker = self._bybit_service.get_raw_ticker(symbol_meta["symbol"])
        wallet = self._bybit_service.get_wallet_snapshot()
        market_price = self._positive_decimal(
            ticker.get("result", {}).get("list", [{}])[0].get("markPrice")
            or ticker.get("result", {}).get("list", [{}])[0].get("lastPrice"),
            "Market price is unavailable.",
        )

        stop_loss, take_profit = self._resolve_protection_prices(
            direction=payload.direction,
            mode=payload.mode,
            timeframe=payload.timeframe,
            market_price=market_price,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
        )

        constraints = self._instrument_constraints(symbol_meta["instrument"])
        rounded_stop = self._rounded_protection_price(
            stop_loss,
            constraints["tickSize"],
            payload.direction,
            "SL",
        )
        rounded_take = self._rounded_protection_price(
            take_profit,
            constraints["tickSize"],
            payload.direction,
            "TP",
        )
        self._validate_price_order(payload.direction, market_price, rounded_stop, rounded_take)

        risk_distance = abs(market_price - rounded_stop)
        if risk_distance <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Risk distance must be greater than zero.",
            )

        available_balance = wallet["available"]
        if available_balance <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bybit Demo available USDT balance is zero.",
            )

        risk_amount = available_balance * (
            Decimal(str(settings_state.risk_per_trade_pct)) / Decimal("100")
        )
        qty = self._round_to_step(
            risk_amount / risk_distance,
            constraints["qtyStep"],
            ROUND_DOWN,
        )

        if qty <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Calculated quantity is zero after exchange rounding.",
            )
        if qty < constraints["minQty"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Calculated quantity {qty} is below Bybit minimum "
                    f"{constraints['minQty']} for {symbol_meta['symbol']}."
                ),
            )
        if constraints["maxQty"] > 0 and qty > constraints["maxQty"]:
            qty = self._round_to_step(
                constraints["maxQty"], constraints["qtyStep"], ROUND_DOWN
            )

        notional = qty * market_price
        if constraints["minNotional"] > 0 and notional < constraints["minNotional"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Calculated order value {notional} USDT is below Bybit minimum "
                    f"{constraints['minNotional']} USDT for {symbol_meta['symbol']}."
                ),
            )

        planned_risk_usdt = qty * risk_distance
        if planned_risk_usdt > risk_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Calculated risk {planned_risk_usdt} USDT exceeds the configured "
                    f"risk budget {risk_amount} USDT."
                ),
            )

        risk_reward = self._risk_reward(
            payload.direction,
            market_price,
            rounded_stop,
            rounded_take,
        )
        if risk_reward < Decimal("2"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Risk-reward {risk_reward:.2f} is below the required minimum 2.00.",
            )

        side = "Buy" if payload.direction == Direction.BUY else "Sell"
        qty_string = self._format_decimal(qty, constraints["qtyStep"])
        rounded_stop_string = self._format_decimal(
            rounded_stop, constraints["tickSize"]
        )
        rounded_take_string = self._format_decimal(
            rounded_take, constraints["tickSize"]
        )
        order_payload = {
            "category": "linear",
            "symbol": symbol_meta["symbol"],
            "side": side,
            "orderType": "Market",
            "qty": qty_string,
            "timeInForce": "IOC",
            "positionIdx": 0,
            "stopLoss": rounded_stop_string,
            "takeProfit": rounded_take_string,
            "slTriggerBy": "MarkPrice",
            "tpTriggerBy": "MarkPrice",
        }

        try:
            order = self._bybit_service.create_private_order(order_payload)
        except HTTPException as exc:
            self._log_execution_failure(
                symbol=symbol_meta["symbol"],
                side=side,
                qty=qty_string,
                market_price=market_price,
                stop_loss=rounded_stop,
                take_profit=rounded_take,
                planned_risk=planned_risk_usdt,
                detail=exc.detail,
                status_code=exc.status_code,
            )
            raise

        order_id = order.get("result", {}).get("orderId")
        if not order_id:
            detail = "Bybit accepted the request but returned no orderId."
            self._log_execution_failure(
                symbol=symbol_meta["symbol"],
                side=side,
                qty=qty_string,
                market_price=market_price,
                stop_loss=rounded_stop,
                take_profit=rounded_take,
                planned_risk=planned_risk_usdt,
                detail=detail,
                status_code=status.HTTP_502_BAD_GATEWAY,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=detail,
            )

        response = ManualTradeResponse(
            message="Manual Bybit demo trade submitted successfully.",
            data=ManualTradeData(
                status="submitted",
                order_id=order_id,
                symbol=symbol_meta["symbol"],
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
            symbol=response.data.symbol,
            mode=payload.mode,
            direction=payload.direction,
            entry_price=response.data.market_price,
            stop_loss=response.data.stop_loss,
            take_profit=response.data.take_profit,
            timeframe=payload.timeframe,
            notional=float(notional),
            planned_risk_usdt=float(planned_risk_usdt),
            risk_reward=float(risk_reward),
            signal_id=signal_id,
            order_id=response.data.order_id,
            qty=response.data.qty,
        )
        if self._repository is not None:
            self._repository.append_log(
                "execution_logs",
                "order_submitted",
                {
                    **response.model_dump(mode="json"),
                    "signal_id": signal_id,
                    "planned_risk_usdt": float(planned_risk_usdt),
                    "risk_budget_usdt": float(risk_amount),
                },
            )
        return response

    def execute_strategy_trade(
        self,
        *,
        symbol: str,
        direction: Direction,
        mode: TradingMode,
        timeframe: Timeframe | None,
        signal_id: str | None = None,
    ) -> ManualTradeResponse:
        return self.execute_manual_trade(
            ManualTradeRequest(
                symbol=symbol,
                direction=direction,
                mode=mode,
                timeframe=timeframe,
            ),
            signal_id=signal_id,
        )

    def _log_execution_failure(
        self,
        *,
        symbol: str,
        side: str,
        qty: str,
        market_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        planned_risk: Decimal,
        detail,
        status_code: int,
    ) -> None:
        safe_detail = detail if isinstance(detail, (str, dict, list)) else str(detail)
        payload = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "market_price": float(market_price),
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit),
            "planned_risk_usdt": float(planned_risk),
            "status_code": status_code,
            "detail": safe_detail,
        }
        logger.warning("Bybit order rejected: %s", payload)
        if self._repository is not None:
            self._repository.append_log(
                "execution_logs",
                "order_rejected",
                payload,
            )

    def _resolve_protection_prices(
        self,
        direction: Direction,
        mode: TradingMode,
        timeframe: Timeframe | None,
        market_price: Decimal,
        stop_loss: float | None,
        take_profit: float | None,
    ) -> tuple[Decimal, Decimal]:
        timeframe_risk_map: dict[Timeframe, Decimal] = {
            Timeframe.M1: Decimal("0.0035"),
            Timeframe.M5: Decimal("0.0045"),
            Timeframe.M15: Decimal("0.0075"),
            Timeframe.H1: Decimal("0.0125"),
        }
        default_risk_pct = (
            Decimal("0.0045")
            if mode == TradingMode.SCALPING
            else Decimal("0.0085")
        )
        risk_pct = timeframe_risk_map.get(timeframe, default_risk_pct)

        if stop_loss is None and take_profit is None:
            if direction == Direction.BUY:
                return (
                    market_price * (Decimal("1") - risk_pct),
                    market_price * (Decimal("1") + risk_pct * Decimal("2")),
                )
            return (
                market_price * (Decimal("1") + risk_pct),
                market_price * (Decimal("1") - risk_pct * Decimal("2")),
            )

        if stop_loss is None or take_profit is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide both stop loss and take profit, or leave both empty.",
            )

        return (
            self._positive_decimal(stop_loss, "Stop loss is invalid."),
            self._positive_decimal(take_profit, "Take profit is invalid."),
        )

    @staticmethod
    def _positive_decimal(value: str | float | int | Decimal, message: str) -> Decimal:
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=message
            ) from exc
        if decimal_value <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
        return decimal_value

    @staticmethod
    def _round_to_step(value: Decimal, step: Decimal, rounding: str) -> Decimal:
        if step <= 0:
            return value
        units = (value / step).to_integral_value(rounding=rounding)
        return (units * step).normalize()

    @staticmethod
    def _format_decimal(value: Decimal, step: Decimal) -> str:
        normalized = step.normalize()
        decimals = abs(normalized.as_tuple().exponent) if normalized.as_tuple().exponent < 0 else 0
        return f"{value:.{decimals}f}"

    @staticmethod
    def _instrument_constraints(instrument: dict) -> dict[str, Decimal]:
        lot_size = instrument.get("lotSizeFilter", {})
        price_filter = instrument.get("priceFilter", {})
        try:
            return {
                "tickSize": Decimal(str(price_filter.get("tickSize") or "0")),
                "qtyStep": Decimal(str(lot_size.get("qtyStep") or "0")),
                "minQty": Decimal(str(lot_size.get("minOrderQty") or "0")),
                "maxQty": Decimal(
                    str(
                        lot_size.get("maxMktOrderQty")
                        or lot_size.get("maxOrderQty")
                        or "0"
                    )
                ),
                "minNotional": Decimal(
                    str(lot_size.get("minNotionalValue") or "0")
                ),
            }
        except InvalidOperation as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Bybit returned invalid instrument constraints.",
            ) from exc

    @staticmethod
    def _rounded_protection_price(
        value: Decimal,
        tick_size: Decimal,
        direction: Direction,
        purpose: str,
    ) -> Decimal:
        if direction == Direction.BUY:
            rounding = ROUND_UP if purpose == "SL" else ROUND_DOWN
        else:
            rounding = ROUND_DOWN if purpose == "SL" else ROUND_UP
        return ManualTradeService._round_to_step(value, tick_size, rounding)

    @staticmethod
    def _validate_price_order(
        direction: Direction,
        market_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
    ) -> None:
        if direction == Direction.BUY and not (stop_loss < market_price < take_profit):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="For long orders the backend requires SL < market < TP.",
            )
        if direction == Direction.SELL and not (take_profit < market_price < stop_loss):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="For short orders the backend requires TP < market < SL.",
            )

    @staticmethod
    def _risk_reward(
        direction: Direction,
        market_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
    ) -> Decimal:
        if direction == Direction.BUY:
            risk_distance = market_price - stop_loss
            reward_distance = take_profit - market_price
        else:
            risk_distance = stop_loss - market_price
            reward_distance = market_price - take_profit
        return reward_distance / risk_distance if risk_distance > 0 else Decimal("0")
