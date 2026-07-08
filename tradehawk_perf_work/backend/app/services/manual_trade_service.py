from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP

from fastapi import HTTPException, status

from app.core.enums import Direction, Timeframe, TradingMode
from app.schemas.trades import ManualTradeData, ManualTradeRequest, ManualTradeResponse
from app.services.bybit_service import BybitService
from app.services.settings_service import SettingsService
from app.services.trade_service import TradeService


class ManualTradeService:
    def __init__(
        self,
        settings_service: SettingsService,
        bybit_service: BybitService,
        trade_service: TradeService,
    ) -> None:
        self._settings_service = settings_service
        self._bybit_service = bybit_service
        self._trade_service = trade_service

    def execute_manual_trade(self, payload: ManualTradeRequest) -> ManualTradeResponse:
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
        normalized_symbol = payload.symbol.strip().upper()
        self._validate_execution_gate(
            symbol=normalized_symbol,
            max_open_positions=settings_state.max_open_positions,
            daily_max_trades=settings_state.daily_max_trades,
            daily_max_loss=settings_state.daily_max_loss,
        )

        connection = self._bybit_service.get_connection_status().data
        if connection.code != "CONNECTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bybit Demo must be connected before sending manual orders.",
            )

        symbol_meta = self._bybit_service.get_validated_symbol(normalized_symbol)
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
        risk_amount = self._resolve_allowed_risk_amount(
            available_balance=available_balance,
            risk_per_trade_pct=settings_state.risk_per_trade_pct,
            daily_max_loss=settings_state.daily_max_loss,
        )
        qty = self._round_to_step(risk_amount / risk_distance, constraints["qtyStep"], ROUND_DOWN)
        max_cash_qty = self._round_to_step(available_balance / market_price, constraints["qtyStep"], ROUND_DOWN)
        if max_cash_qty > 0 and qty > max_cash_qty:
            qty = max_cash_qty

        if qty <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Calculated quantity is zero after exchange rounding.",
            )
        if qty < constraints["minQty"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Calculated quantity {qty} is below the minimum order size.",
            )
        if constraints["maxQty"] > 0 and qty > constraints["maxQty"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Calculated quantity {qty} exceeds the maximum order size.",
            )

        side = "Buy" if payload.direction == Direction.BUY else "Sell"
        qty_string = self._format_decimal(qty, constraints["qtyStep"])
        rounded_stop_string = self._format_decimal(rounded_stop, constraints["tickSize"])
        rounded_take_string = self._format_decimal(rounded_take, constraints["tickSize"])

        order = self._bybit_service.create_private_order(
            {
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
        )
        order_id = order.get("result", {}).get("orderId")
        notional = qty * market_price
        planned_risk_usdt = qty * risk_distance
        risk_pct_of_entry = (risk_distance / market_price) * Decimal("100")
        risk_reward = self._risk_reward(payload.direction, market_price, rounded_stop, rounded_take)
        self._validate_planned_risk_budget(
            planned_risk_usdt=planned_risk_usdt,
            daily_max_loss=settings_state.daily_max_loss,
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
                planned_risk_usdt=float(planned_risk_usdt),
                risk_distance=float(risk_distance),
                risk_pct_of_entry=float(risk_pct_of_entry),
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
            risk_distance=float(risk_distance),
            risk_pct_of_entry=float(risk_pct_of_entry),
            risk_reward=float(risk_reward),
            order_id=response.data.order_id,
            qty=response.data.qty,
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
        default_risk_pct = Decimal("0.0045") if mode == TradingMode.SCALPING else Decimal("0.0085")
        risk_pct = timeframe_risk_map.get(timeframe, default_risk_pct)

        if stop_loss is None or take_profit is None:
            if direction == Direction.BUY:
                generated_sl = market_price * (Decimal("1") - risk_pct)
                generated_tp = market_price * (Decimal("1") + (risk_pct * Decimal("2")))
            else:
                generated_sl = market_price * (Decimal("1") + risk_pct)
                generated_tp = market_price * (Decimal("1") - (risk_pct * Decimal("2")))
            return generated_sl, generated_tp

        return self._positive_decimal(stop_loss, "Stop loss is invalid."), self._positive_decimal(
            take_profit, "Take profit is invalid."
        )

    @staticmethod
    def _positive_decimal(value: str | float | int | Decimal, message: str) -> Decimal:
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc
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
        decimals = abs(step.normalize().as_tuple().exponent) if step.normalize().as_tuple().exponent < 0 else 0
        return f"{value:.{decimals}f}"

    @staticmethod
    def _instrument_constraints(instrument: dict) -> dict[str, Decimal]:
        lot_size = instrument.get("lotSizeFilter", {})
        price_filter = instrument.get("priceFilter", {})
        return {
            "tickSize": Decimal(str(price_filter.get("tickSize"))),
            "qtyStep": Decimal(str(lot_size.get("qtyStep"))),
            "minQty": Decimal(str(lot_size.get("minOrderQty"))),
            "maxQty": Decimal(str(lot_size.get("maxOrderQty") or lot_size.get("maxMktOrderQty") or "0")),
        }

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

    def _validate_execution_gate(
        self,
        *,
        symbol: str,
        max_open_positions: int,
        daily_max_trades: int,
        daily_max_loss: float,
    ) -> None:
        if max_open_positions <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Set max active slots above 0 before sending manual orders.",
            )
        if daily_max_trades <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Set daily max trades above 0 before sending manual orders.",
            )
        if self._trade_service.get_open_trade_count() >= max_open_positions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max active slots reached.",
            )
        if self._trade_service.get_daily_trade_count() >= daily_max_trades:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Daily max trades limit reached.",
            )
        if self._trade_service.has_open_trade_for_symbol(symbol):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{symbol} already has an active trade.",
            )
        remaining_daily_loss = self._trade_service.get_remaining_daily_loss_budget(daily_max_loss)
        if remaining_daily_loss is not None and remaining_daily_loss <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Daily max loss limit already reached.",
            )

    def _resolve_allowed_risk_amount(
        self,
        *,
        available_balance: Decimal,
        risk_per_trade_pct: float,
        daily_max_loss: float,
    ) -> Decimal:
        risk_amount = available_balance * (Decimal(str(risk_per_trade_pct)) / Decimal("100"))
        remaining_daily_loss = self._trade_service.get_remaining_daily_loss_budget(daily_max_loss)
        if remaining_daily_loss is not None:
            risk_amount = min(risk_amount, Decimal(str(remaining_daily_loss)))
        if risk_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No remaining risk budget is available for a new trade.",
            )
        return risk_amount

    def _validate_planned_risk_budget(
        self,
        *,
        planned_risk_usdt: Decimal,
        daily_max_loss: float,
    ) -> None:
        remaining_daily_loss = self._trade_service.get_remaining_daily_loss_budget(daily_max_loss)
        if remaining_daily_loss is None:
            return
        if float(planned_risk_usdt) > remaining_daily_loss:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Planned risk {float(planned_risk_usdt):.2f} exceeds remaining daily "
                    f"loss budget {remaining_daily_loss:.2f}."
                ),
            )
