from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.enums import TradingMode
from app.schemas.workflow import (
    WorkflowOrderSnapshot,
    WorkflowSignalSnapshot,
    WorkflowStatusData,
    WorkflowStatusResponse,
)
from app.services.bybit_service import BybitService
from app.services.manual_trade_service import ManualTradeService
from app.services.settings_service import SettingsService
from app.services.strategy_service import StrategyService
from app.services.trade_service import TradeService


class AutoTradeService:
    def __init__(
        self,
        settings_service: SettingsService,
        bybit_service: BybitService,
        strategy_service: StrategyService,
        manual_trade_service: ManualTradeService,
        trade_service: TradeService,
    ) -> None:
        self._settings_service = settings_service
        self._bybit_service = bybit_service
        self._strategy_service = strategy_service
        self._manual_trade_service = manual_trade_service
        self._trade_service = trade_service
        self._last_scanner_status = "idle"
        self._last_signal_status = "idle"
        self._last_execution_status = "idle"
        self._last_reject_reason: str | None = None
        self._last_candidate_signal: WorkflowSignalSnapshot | None = None
        self._last_order: WorkflowOrderSnapshot | None = None
        self._last_cycle_at: str | None = None

    def run_cycle(self) -> dict[str, int | str]:
        settings = self._settings_service.get_settings_state()
        self._last_cycle_at = datetime.now(timezone.utc).isoformat()
        self._last_candidate_signal = None
        self._last_order = None
        self._last_reject_reason = None
        self._last_scanner_status = "idle"
        self._last_signal_status = "idle"
        self._last_execution_status = "idle"
        self._trade_service.sync_with_exchange(self._bybit_service)
        if not settings.auto_trade_enabled or settings.emergency_stop:
            self._last_execution_status = "idle"
            self._last_reject_reason = (
                "Emergency stop is active." if settings.emergency_stop else "Auto trade is off."
            )
            return {"status": "idle", "opened": 0}

        if settings.system_mode != "demo":
            self._last_execution_status = "blocked"
            self._last_reject_reason = "System mode is not demo."
            return {"status": "locked_mode", "opened": 0}

        if settings.active_strategy_mode == TradingMode.SCALPING and not settings.scalping_engine_enabled:
            self._last_execution_status = "blocked"
            self._last_reject_reason = "Scalping engine is disabled."
            return {"status": "engine_disabled", "opened": 0}
        if settings.active_strategy_mode == TradingMode.INTRADAY and not settings.intraday_engine_enabled:
            self._last_execution_status = "blocked"
            self._last_reject_reason = "Intraday engine is disabled."
            return {"status": "engine_disabled", "opened": 0}

        bybit_status = self._bybit_service.get_connection_status().data
        if bybit_status.code != "CONNECTED":
            self._last_execution_status = "blocked"
            self._last_reject_reason = bybit_status.detail
            return {"status": "exchange_disconnected", "opened": 0}

        remaining_slots = settings.max_open_positions - self._trade_service.get_open_trade_count()
        remaining_daily = settings.daily_max_trades - self._trade_service.get_daily_trade_count()
        capacity = min(remaining_slots, remaining_daily)
        if capacity <= 0:
            self._last_execution_status = "blocked"
            self._last_reject_reason = "Risk limits reached for slots or daily trades."
            return {"status": "limits_reached", "opened": 0}

        opened = 0
        selected_mode = settings.active_strategy_mode
        timeframe = self._strategy_service.default_timeframe(selected_mode)
        symbols = self._strategy_service.default_symbols(selected_mode)
        self._last_scanner_status = f"scanned_{len(symbols)}_symbols"

        for symbol in symbols:
            if opened >= capacity:
                break
            if self._trade_service.has_open_trade_for_symbol(symbol):
                self._last_reject_reason = f"{symbol} already has an open trade."
                continue
            try:
                signal = self._strategy_service.evaluate_symbol(
                    symbol=symbol,
                    mode=selected_mode,
                    timeframe=timeframe,
                )
            except HTTPException:
                continue

            if signal is None or signal.grade not in settings.allowed_signal_grades:
                if signal is not None:
                    self._last_candidate_signal = WorkflowSignalSnapshot(
                        symbol=signal.symbol,
                        direction=signal.direction.value,
                        grade=signal.grade.value,
                        timeframe=signal.timeframe.value,
                        reason=signal.reason,
                    )
                    self._last_signal_status = "filtered"
                    self._last_reject_reason = f"{signal.grade.value} is not allowed by current risk profile."
                continue

            self._last_candidate_signal = WorkflowSignalSnapshot(
                symbol=signal.symbol,
                direction=signal.direction.value,
                grade=signal.grade.value,
                timeframe=signal.timeframe.value,
                reason=signal.reason,
            )
            self._last_signal_status = "candidate_ready"
            signal_id = self._trade_service.build_signal_id(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                direction=signal.direction,
            )
            if self._trade_service.was_signal_executed(signal_id):
                self._last_reject_reason = f"{signal.symbol} signal already executed today."
                continue

            try:
                order = self._manual_trade_service.execute_strategy_trade(
                    symbol=signal.symbol,
                    direction=signal.direction,
                    mode=signal.mode,
                    timeframe=signal.timeframe,
                    signal_id=signal_id,
                )
            except HTTPException:
                self._last_execution_status = "rejected"
                self._last_reject_reason = "Exchange rejected the candidate order."
                continue
            except Exception as exc:
                self._last_execution_status = "rejected"
                self._last_reject_reason = f"Unexpected execution error: {exc}"
                continue

            self._last_order = WorkflowOrderSnapshot(
                symbol=order.data.symbol,
                side=order.data.side,
                qty=order.data.qty,
                order_id=order.data.order_id,
                status=order.data.status,
            )
            self._last_execution_status = "submitted"
            opened += 1

        if opened == 0 and self._last_signal_status == "idle":
            self._last_signal_status = "no_signal"
            self._last_reject_reason = self._last_reject_reason or "Scanner found no executable signal."

        return {
            "status": "executed" if opened else "no_match",
            "opened": opened,
        }

    def get_workflow_status(self) -> WorkflowStatusResponse:
        settings = self._settings_service.get_settings_state()
        bybit_status = self._bybit_service.get_connection_status().data
        return WorkflowStatusResponse(
            message="Workflow status fetched successfully.",
            data=WorkflowStatusData(
                backend_health="healthy",
                selected_mode=settings.active_strategy_mode,
                scanner_status=self._last_scanner_status,
                signal_status=self._last_signal_status,
                execution_status=self._last_execution_status,
                auto_trade_enabled=settings.auto_trade_enabled,
                bybit_connection_code=bybit_status.code,
                active_trade_count=self._trade_service.get_open_trade_count(),
                daily_trade_count=self._trade_service.get_daily_trade_count(),
                candidate_signal=self._last_candidate_signal,
                last_order=self._last_order,
                last_reject_reason=self._last_reject_reason,
                last_cycle_at=self._last_cycle_at,
            ),
        )
