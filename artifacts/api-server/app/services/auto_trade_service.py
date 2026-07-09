import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from app.db.repository import PersistenceRepository
from app.schemas.workflow import (
    WorkflowOrderSnapshot,
    WorkflowSignalSnapshot,
    WorkflowStatusData,
    WorkflowStatusResponse,
)
from app.services.bybit_service import BybitService
from app.services.manual_trade_service import ManualTradeService
from app.services.settings_service import SettingsService
from app.services.signal_registry import SignalRegistry
from app.services.strategy_service import StrategyService
from app.services.trade_service import TradeService


logger = logging.getLogger(__name__)


class AutoTradeService:
    def __init__(
        self,
        settings_service: SettingsService,
        bybit_service: BybitService,
        strategy_service: StrategyService,
        manual_trade_service: ManualTradeService,
        trade_service: TradeService,
        signal_registry: SignalRegistry,
        repository: PersistenceRepository | None = None,
    ) -> None:
        self._settings_service = settings_service
        self._bybit_service = bybit_service
        self._strategy_service = strategy_service
        self._manual_trade_service = manual_trade_service
        self._trade_service = trade_service
        self._signal_registry = signal_registry
        self._repository = repository
        self._last_scanner_status = "idle"
        self._last_signal_status = "idle"
        self._last_execution_status = "idle"
        self._last_reject_reason: str | None = None
        self._last_candidate_signal: WorkflowSignalSnapshot | None = None
        self._last_order: WorkflowOrderSnapshot | None = None
        self._last_cycle_at: str | None = None
        self._restore_state()

    def run_cycle(self) -> dict[str, int | str]:
        settings = self._settings_service.get_settings_state()
        self._last_cycle_at = datetime.now(timezone.utc).isoformat()
        self._last_candidate_signal = None
        self._last_order = None
        self._last_reject_reason = None
        self._last_scanner_status = "idle"
        self._last_signal_status = "idle"
        self._last_execution_status = "idle"

        try:
            self._trade_service.sync_with_exchange(self._bybit_service)

            execution_ready, block_reason = self._settings_service.get_execution_readiness()
            if not execution_ready:
                self._last_execution_status = (
                    "idle" if not settings.auto_trade_enabled else "blocked"
                )
                self._last_reject_reason = block_reason
                return {
                    "status": "idle" if not settings.auto_trade_enabled else "not_ready",
                    "opened": 0,
                }

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
            evaluated_signals = []

            for symbol in symbols:
                try:
                    signal = self._strategy_service.evaluate_symbol(
                        symbol=symbol,
                        mode=selected_mode,
                        timeframe=timeframe,
                    )
                except HTTPException as exc:
                    self._last_reject_reason = self._format_http_detail(exc.detail)
                    continue

                if signal is None:
                    continue
                evaluated_signals.append(signal)

                if opened >= capacity:
                    continue
                if self._trade_service.has_open_trade_for_symbol(symbol):
                    self._last_reject_reason = f"{symbol} already has an open trade."
                    continue

                self._last_candidate_signal = WorkflowSignalSnapshot(
                    symbol=signal.symbol,
                    direction=signal.direction.value,
                    grade=signal.grade.value,
                    timeframe=signal.timeframe.value,
                    reason=signal.reason,
                )

                if signal.grade not in settings.allowed_signal_grades:
                    self._last_signal_status = "filtered"
                    self._last_reject_reason = (
                        f"{signal.grade.value} is not allowed by current risk profile."
                    )
                    continue

                self._last_signal_status = "candidate_ready"
                signal_id = self._trade_service.build_signal_id(
                    symbol=signal.symbol,
                    timeframe=signal.timeframe,
                    direction=signal.direction,
                )
                if self._trade_service.was_signal_executed(signal_id):
                    self._last_reject_reason = (
                        f"{signal.symbol} signal already executed today."
                    )
                    continue

                try:
                    order = self._manual_trade_service.execute_strategy_trade(
                        symbol=signal.symbol,
                        direction=signal.direction,
                        mode=signal.mode,
                        timeframe=signal.timeframe,
                        signal_id=signal_id,
                    )
                except HTTPException as exc:
                    self._last_execution_status = "rejected"
                    self._last_reject_reason = self._format_http_detail(exc.detail)
                    continue
                except Exception as exc:
                    self._last_execution_status = "rejected"
                    self._last_reject_reason = f"Unexpected execution error: {exc}"
                    logger.exception("Unexpected auto-trade execution error")
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

            self._signal_registry.replace(
                selected_mode,
                evaluated_signals,
                source="auto_trade_cycle",
            )

            if not evaluated_signals:
                self._last_signal_status = "no_signal"
                self._last_reject_reason = (
                    self._last_reject_reason or "Scanner found no executable signal."
                )
            elif opened == 0 and self._last_signal_status == "idle":
                self._last_signal_status = "filtered"

            return {
                "status": "executed" if opened else "no_match",
                "opened": opened,
            }
        finally:
            self._persist_state()

    def get_workflow_status(self) -> WorkflowStatusResponse:
        settings = self._settings_service.get_settings_state()
        bybit_status = self._bybit_service.get_connection_status().data
        execution_ready, block_reason = self._settings_service.get_execution_readiness()

        execution_status = self._last_execution_status
        reject_reason = self._last_reject_reason
        if not execution_ready:
            execution_status = "idle" if not settings.auto_trade_enabled else "blocked"
            reject_reason = block_reason

        return WorkflowStatusResponse(
            message="Workflow status fetched successfully.",
            data=WorkflowStatusData(
                backend_health="healthy",
                selected_mode=settings.active_strategy_mode,
                scanner_status=self._last_scanner_status,
                signal_status=self._last_signal_status,
                execution_status=execution_status,
                execution_ready=execution_ready,
                execution_block_reason=block_reason,
                auto_trade_enabled=settings.auto_trade_enabled,
                bybit_connection_code=bybit_status.code,
                active_trade_count=self._trade_service.get_open_trade_count(),
                daily_trade_count=self._trade_service.get_daily_trade_count(),
                candidate_signal=self._last_candidate_signal,
                last_order=self._last_order,
                last_reject_reason=reject_reason,
                last_cycle_at=self._last_cycle_at,
            ),
        )

    @staticmethod
    def _format_http_detail(detail) -> str:
        if isinstance(detail, str):
            return detail
        if isinstance(detail, dict):
            code = detail.get("code") or detail.get("retCode")
            message = detail.get("message") or detail.get("retMsg") or str(detail)
            return f"Bybit code {code}: {message}" if code is not None else message
        return str(detail)

    def _restore_state(self) -> None:
        if self._repository is None:
            return
        stored = self._repository.load_workflow_state()
        if not stored:
            return
        try:
            self._last_scanner_status = str(stored.get("scanner_status") or "idle")
            self._last_signal_status = str(stored.get("signal_status") or "idle")
            self._last_execution_status = str(stored.get("execution_status") or "idle")
            self._last_reject_reason = stored.get("last_reject_reason")
            self._last_cycle_at = stored.get("last_cycle_at")
            candidate = stored.get("candidate_signal")
            order = stored.get("last_order")
            self._last_candidate_signal = (
                WorkflowSignalSnapshot.model_validate(candidate) if candidate else None
            )
            self._last_order = (
                WorkflowOrderSnapshot.model_validate(order) if order else None
            )
        except Exception as exc:
            logger.warning("Stored workflow state was ignored: %s", exc)

    def _persist_state(self) -> None:
        if self._repository is None:
            return
        self._repository.save_workflow_state(
            {
                "scanner_status": self._last_scanner_status,
                "signal_status": self._last_signal_status,
                "execution_status": self._last_execution_status,
                "candidate_signal": (
                    self._last_candidate_signal.model_dump(mode="json")
                    if self._last_candidate_signal
                    else None
                ),
                "last_order": (
                    self._last_order.model_dump(mode="json")
                    if self._last_order
                    else None
                ),
                "last_reject_reason": self._last_reject_reason,
                "last_cycle_at": self._last_cycle_at,
            }
        )
