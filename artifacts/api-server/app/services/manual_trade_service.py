import logging
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP

from fastapi import HTTPException, status

from app.core.enums import Direction, Timeframe, TradingMode
from app.core.trading_clock import is_on_trading_date, trading_date
from app.core.trading_rules import COMBINED_DAILY_MAX_LOSS_PCT, trading_rule
from app.db.repository import PersistenceRepository
from app.schemas.trades import ManualTradeData, ManualTradeRequest, ManualTradeResponse
from app.services.bybit_service import BybitService
from app.services.profit_tracking_service import ProfitTrackingService
from app.services.risk_execution_guard import RiskExecutionGuard
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
        profit_tracking_service: ProfitTrackingService | None = None,
        risk_execution_guard: RiskExecutionGuard | None = None,
    ) -> None:
        self._settings_service = settings_service
        self._bybit_service = bybit_service
        self._trade_service = trade_service
        self._repository = repository
        self._profit_tracking_service = profit_tracking_service
        self._risk_execution_guard = risk_execution_guard

    def execute_manual_trade(
        self,
        payload: ManualTradeRequest,
        signal_id: str | None = None,
    ) -> ManualTradeResponse:
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
        rounded_stop = self._rounded_protection_price(
            stop_loss, constraints["tickSize"], payload.direction, "SL"
        )
        rounded_take = self._rounded_protection_price(
            take_profit, constraints["tickSize"], payload.direction, "TP"
        )
        self._validate_price_order(payload.direction, market_price, rounded_stop, rounded_take)

        risk_distance = abs(market_price - rounded_stop)
        account_equity = Decimal(str(wallet["equity"]))
        available_balance = Decimal(str(wallet["available"]))
        if account_equity <= 0 or available_balance <= 0 or risk_distance <= 0:
            raise HTTPException(status_code=400, detail="Balance or risk distance is invalid.")

        rule = trading_rule(payload.mode)
        configured_risk_budget = (
            account_equity
            * rule.risk_per_trade_pct
            / Decimal("100")
        )
        risk_budget = self._apply_v2_daily_loss_guard(
            configured_risk_budget,
            payload.mode,
            account_equity,
        )
        risk_budget = self._apply_profit_lock_guard(risk_budget)

        qty = self._round_to_step(
            risk_budget / risk_distance,
            constraints["qtyStep"],
            ROUND_DOWN,
        )
        if qty <= 0 or qty < constraints["minQty"]:
            raise HTTPException(
                status_code=400,
                detail=f"Calculated quantity {qty} is below Bybit minimum {constraints['minQty']}.",
            )
        if constraints["maxQty"] > 0 and qty > constraints["maxQty"]:
            qty = self._round_to_step(
                constraints["maxQty"], constraints["qtyStep"], ROUND_DOWN
            )

        notional = qty * market_price
        if constraints["minNotional"] > 0 and notional < constraints["minNotional"]:
            raise HTTPException(
                status_code=400,
                detail=f"Order value {notional} is below Bybit minimum {constraints['minNotional']}.",
            )

        planned_risk = qty * risk_distance
        if planned_risk > risk_budget:
            raise HTTPException(status_code=400, detail="Planned risk exceeds approved risk budget.")
        self._validate_margin_and_exposure(
            mode=payload.mode,
            account_equity=account_equity,
            available_balance=available_balance,
            notional=notional,
            planned_risk=planned_risk,
        )
        risk_reward = self._risk_reward(
            payload.direction, market_price, rounded_stop, rounded_take
        )
        if risk_reward < rule.minimum_risk_reward:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Risk-reward {risk_reward:.2f} is below "
                    f"{rule.minimum_risk_reward:.2f}."
                ),
            )

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
            leverage_setter = getattr(self._bybit_service, "set_symbol_leverage", None)
            if callable(leverage_setter):
                leverage_setter(symbol, rule.leverage)
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
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Bybit returned no orderId.",
            )

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
                "configured_risk_budget_usdt": float(configured_risk_budget),
                "approved_risk_budget_usdt": float(risk_budget),
                "account_equity_usdt": float(account_equity),
                "v2_risk_per_trade_pct": float(rule.risk_per_trade_pct),
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

    def _apply_profit_lock_guard(self, configured_risk_budget: Decimal) -> Decimal:
        if self._profit_tracking_service is None or self._risk_execution_guard is None:
            return configured_risk_budget

        profit_state = self._profit_tracking_service.refresh_from_sources(
            self._trade_service,
            self._bybit_service,
        )
        active_data = self._trade_service.get_active_trades().data
        active_records = [*active_data.scalping_trades, *active_data.intraday_trades]
        active_planned_risk = sum(
            float(trade.planned_risk_usdt or 0.0) for trade in active_records
        )
        decision = self._risk_execution_guard.evaluate(
            configured_risk_budget=float(configured_risk_budget),
            profit_state=profit_state,
            active_planned_risk=active_planned_risk,
        )
        self._log(
            "profit_lock_risk_check",
            {
                "allowed": decision.allowed,
                "configured_risk_budget_usdt": decision.configured_risk_budget,
                "approved_risk_budget_usdt": decision.approved_risk_budget,
                "available_lock_cushion_usdt": decision.available_lock_cushion,
                "active_planned_risk_usdt": decision.active_planned_risk,
                "daily_realized_pct": profit_state.daily_realized_pct,
                "daily_locked_floor_pct": decision.locked_floor_pct,
                "reason": decision.reason,
            },
        )
        if not decision.allowed:
            raise HTTPException(status_code=400, detail=decision.reason)
        return Decimal(str(decision.approved_risk_budget))

    def _apply_daily_loss_guard(
        self,
        configured_risk_budget: Decimal,
        daily_max_loss: float,
    ) -> Decimal:
        remaining = self._trade_service.get_remaining_daily_loss_budget(
            daily_max_loss
        )
        if remaining <= 0:
            raise HTTPException(status_code=400, detail="Daily max loss limit reached.")
        return min(configured_risk_budget, Decimal(str(remaining)))

    def _apply_v2_daily_loss_guard(
        self,
        configured_risk_budget: Decimal,
        mode: TradingMode,
        account_equity: Decimal,
    ) -> Decimal:
        combined_budget = account_equity * COMBINED_DAILY_MAX_LOSS_PCT / Decimal("100")
        combined_remaining = Decimal(
            str(self._trade_service.get_remaining_daily_loss_budget(float(combined_budget)))
        )
        if combined_remaining <= 0:
            raise HTTPException(status_code=400, detail="Combined daily max loss limit reached.")

        rule = trading_rule(mode)
        mode_budget = account_equity * rule.daily_max_net_loss_pct / Decimal("100")
        mode_realized_loss = self._mode_daily_realized_loss(mode)
        mode_remaining = mode_budget - mode_realized_loss
        if mode_remaining <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"{mode.value.title()} daily max loss limit reached.",
            )

        return min(configured_risk_budget, combined_remaining, mode_remaining)

    def _mode_daily_realized_loss(self, mode: TradingMode) -> Decimal:
        today = trading_date()
        response = self._trade_service.get_closed_trades()
        loss = Decimal("0")
        for trade in response.data.closed_trades:
            if trade.mode != mode or not is_on_trading_date(trade.closed_time, today):
                continue
            realized = Decimal(str(trade.realized_pnl or 0))
            if realized < 0:
                loss += abs(realized)
        return loss

    def _validate_margin_and_exposure(
        self,
        *,
        mode: TradingMode,
        account_equity: Decimal,
        available_balance: Decimal,
        notional: Decimal,
        planned_risk: Decimal,
    ) -> None:
        rule = trading_rule(mode)
        leverage = Decimal(str(rule.leverage))
        if leverage <= 0:
            raise HTTPException(status_code=400, detail="Configured leverage is invalid.")

        active_notional, active_planned_risk = self._active_position_totals()
        required_margin = notional / leverage
        if required_margin > available_balance:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Required margin {required_margin:.2f} exceeds available balance "
                    f"{available_balance:.2f} at {rule.leverage}x leverage."
                ),
            )

        exposure_cap = account_equity * leverage
        total_exposure = active_notional + notional
        if total_exposure > exposure_cap:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Total exposure {total_exposure:.2f} exceeds exposure cap "
                    f"{exposure_cap:.2f} at {rule.leverage}x leverage."
                ),
            )

        combined_loss_budget = account_equity * COMBINED_DAILY_MAX_LOSS_PCT / Decimal("100")
        combined_remaining = Decimal(
            str(self._trade_service.get_remaining_daily_loss_budget(float(combined_loss_budget)))
        )
        risk_capacity = combined_remaining - active_planned_risk
        if risk_capacity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Existing open-position risk already uses the remaining daily loss capacity.",
            )
        if planned_risk > risk_capacity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Planned risk {planned_risk:.2f} exceeds remaining risk capacity "
                    f"{risk_capacity:.2f} after existing open-position risk."
                ),
            )

    def _active_position_totals(self) -> tuple[Decimal, Decimal]:
        active = self._trade_service.get_active_trades().data
        active_records = [*active.scalping_trades, *active.intraday_trades]
        total_notional = Decimal("0")
        total_planned_risk = Decimal("0")
        for trade in active_records:
            total_notional += Decimal(str(trade.notional or 0))
            total_planned_risk += Decimal(str(trade.planned_risk_usdt or 0))
        return total_notional, total_planned_risk

    def _resolve_protection_prices(
        self,
        *,
        symbol: str,
        direction: Direction,
        mode: TradingMode,
        timeframe: Timeframe | None,
        market_price: Decimal,
        stop_loss: float | None,
        take_profit: float | None,
    ) -> tuple[Decimal, Decimal]:
        if (stop_loss is None) != (take_profit is None):
            raise HTTPException(
                status_code=400,
                detail="Provide both stop loss and take profit, or leave both empty.",
            )
        if stop_loss is not None and take_profit is not None:
            return (
                self._positive_decimal(stop_loss, "Stop loss is invalid."),
                self._positive_decimal(take_profit, "Take profit is invalid."),
            )

        interval_map = {
            Timeframe.M1: "1",
            Timeframe.M5: "5",
            Timeframe.M15: "15",
            Timeframe.H1: "60",
        }
        selected_timeframe = timeframe or trading_rule(mode).setup_timeframe
        interval = interval_map[selected_timeframe]
        try:
            candles = self._load_ohlc(symbol, interval, 80)
            atr = self._atr(candles, 14)
            if atr is None or len(candles) < 20:
                raise ValueError("insufficient ATR candles")
            recent = candles[-12:]
            swing_low = min(item[2] for item in recent)
            swing_high = max(item[1] for item in recent)
            atr_buffer = atr * Decimal("0.35")
            minimum_distance = max(
                market_price * Decimal("0.0035"), atr * Decimal("0.80")
            )
            maximum_distance = market_price * (
                Decimal("0.025")
                if mode == TradingMode.SCALPING
                else Decimal("0.040")
            )
            structural_stop = (
                swing_low - atr_buffer
                if direction == Direction.BUY
                else swing_high + atr_buffer
            )
            distance = (
                market_price - structural_stop
                if direction == Direction.BUY
                else structural_stop - market_price
            )
            distance = max(minimum_distance, min(distance, maximum_distance))
            generated_sl = (
                market_price - distance
                if direction == Direction.BUY
                else market_price + distance
            )
            generated_tp = (
                market_price + distance * trading_rule(mode).minimum_risk_reward
                if direction == Direction.BUY
                else market_price - distance * trading_rule(mode).minimum_risk_reward
            )
            self._log(
                "protection_generated",
                {
                    "symbol": symbol,
                    "interval": interval,
                    "atr": float(atr),
                    "swing": float(
                        swing_low if direction == Direction.BUY else swing_high
                    ),
                    "stop_loss": float(generated_sl),
                    "take_profit": float(generated_tp),
                },
            )
            return generated_sl, generated_tp
        except Exception as exc:
            fallback_pct = (
                Decimal("0.0065")
                if mode == TradingMode.SCALPING
                else Decimal("0.0100")
            )
            reward_multiple = trading_rule(mode).minimum_risk_reward
            logger.warning("ATR swing fallback for %s: %s", symbol, exc)
            if direction == Direction.BUY:
                return (
                    market_price * (Decimal("1") - fallback_pct),
                    market_price * (Decimal("1") + fallback_pct * reward_multiple),
                )
            return (
                market_price * (Decimal("1") + fallback_pct),
                market_price * (Decimal("1") - fallback_pct * reward_multiple),
            )

    def _load_ohlc(
        self, symbol: str, interval: str, limit: int
    ) -> list[tuple[Decimal, Decimal, Decimal, Decimal]]:
        payload = self._bybit_service._get_closed_klines(
            symbol, interval, limit=limit
        )
        rows = list(reversed(payload.get("result", {}).get("list", [])))
        result = []
        for row in rows:
            try:
                result.append(
                    (
                        Decimal(str(row[1])),
                        Decimal(str(row[2])),
                        Decimal(str(row[3])),
                        Decimal(str(row[4])),
                    )
                )
            except (InvalidOperation, TypeError, ValueError, IndexError):
                continue
        return result

    @staticmethod
    def _atr(
        candles: list[tuple[Decimal, Decimal, Decimal, Decimal]], period: int
    ) -> Decimal | None:
        if len(candles) <= period:
            return None
        ranges = []
        for index in range(1, len(candles)):
            _, high, low, _ = candles[index]
            previous_close = candles[index - 1][3]
            ranges.append(
                max(
                    high - low,
                    abs(high - previous_close),
                    abs(low - previous_close),
                )
            )
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
            "maxQty": Decimal(
                str(lot.get("maxMktOrderQty") or lot.get("maxOrderQty") or "0")
            ),
            "minNotional": Decimal(str(lot.get("minNotionalValue") or "0")),
        }

    @staticmethod
    def _round_to_step(value: Decimal, step: Decimal, rounding: str) -> Decimal:
        if step <= 0:
            return value
        return (
            (value / step).to_integral_value(rounding=rounding) * step
        ).normalize()

    @staticmethod
    def _format_decimal(value: Decimal, step: Decimal) -> str:
        normalized = step.normalize()
        decimals = (
            abs(normalized.as_tuple().exponent)
            if normalized.as_tuple().exponent < 0
            else 0
        )
        return f"{value:.{decimals}f}"

    @staticmethod
    def _rounded_protection_price(
        value: Decimal,
        tick: Decimal,
        direction: Direction,
        purpose: str,
    ) -> Decimal:
        rounding = (
            ROUND_UP
            if (direction == Direction.BUY and purpose == "SL")
            or (direction == Direction.SELL and purpose == "TP")
            else ROUND_DOWN
        )
        return ManualTradeService._round_to_step(value, tick, rounding)

    @staticmethod
    def _validate_price_order(
        direction: Direction,
        market: Decimal,
        stop: Decimal,
        take: Decimal,
    ) -> None:
        valid = (
            stop < market < take
            if direction == Direction.BUY
            else take < market < stop
        )
        if not valid:
            raise HTTPException(status_code=400, detail="Invalid SL/TP price order.")

    @staticmethod
    def _risk_reward(
        direction: Direction,
        market: Decimal,
        stop: Decimal,
        take: Decimal,
    ) -> Decimal:
        risk = market - stop if direction == Direction.BUY else stop - market
        reward = take - market if direction == Direction.BUY else market - take
        return reward / risk if risk > 0 else Decimal("0")
