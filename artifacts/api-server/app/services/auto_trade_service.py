import logging
from datetime import datetime, timezone
from threading import Lock

from fastapi import HTTPException

from app.core.enums import TradingMode
from app.core.trading_clock import is_on_trading_date, trading_date
from app.core.trading_rules import (
    COMBINED_DAILY_MAX_LOSS_PCT,
    COMBINED_MAX_OPEN_TRADES,
    trading_rule,
)
from app.db.repository import PersistenceRepository
from app.schemas.workflow import (
    WorkflowOrderSnapshot,
    WorkflowSignalSnapshot,
    WorkflowStatusData,
    WorkflowStatusResponse,
)
from app.services.bybit_service import BybitService
from app.services.manual_trade_service import ManualTradeService
from app.services.profit_tracking_service import ProfitTrackingService
from app.services.settings_service import SettingsService
from app.services.signal_registry import SignalRegistry
from app.services.strategy_service import StrategyService
from app.services.trade_service import TradeService


logger = logging.getLogger(__name__)


class AutoTradeService:
    MODE_OPEN_LIMITS = {
        TradingMode.SCALPING: COMBINED_MAX_OPEN_TRADES,
        TradingMode.INTRADAY: COMBINED_MAX_OPEN_TRADES,
    }
    MODE_LEVERAGE = {
        TradingMode.SCALPING: 10,
        TradingMode.INTRADAY: 5,
    }
    MODE_REALIZED_LOSS_LIMIT_PCT = {
        TradingMode.SCALPING: -float(trading_rule(TradingMode.SCALPING).daily_max_net_loss_pct),
        TradingMode.INTRADAY: -float(trading_rule(TradingMode.INTRADAY).daily_max_net_loss_pct),
    }
    COMBINED_REALIZED_LOSS_LIMIT_PCT = -float(COMBINED_DAILY_MAX_LOSS_PCT)

    def __init__(
        self,
        settings_service: SettingsService,
        bybit_service: BybitService,
        strategy_service: StrategyService,
        manual_trade_service: ManualTradeService,
        trade_service: TradeService,
        signal_registry: SignalRegistry,
        repository: PersistenceRepository | None = None,
        profit_tracking_service: ProfitTrackingService | None = None,
    ) -> None:
        self._settings_service = settings_service
        self._bybit_service = bybit_service
        self._strategy_service = strategy_service
        self._manual_trade_service = manual_trade_service
        self._trade_service = trade_service
        self._signal_registry = signal_registry
        self._repository = repository
        self._profit_tracking_service = profit_tracking_service
        self._last_scanner_status = "idle"
        self._last_signal_status = "idle"
        self._last_execution_status = "idle"
        self._last_reject_reason: str | None = None
        self._last_candidate_signal: WorkflowSignalSnapshot | None = None
        self._last_order: WorkflowOrderSnapshot | None = None
        self._last_cycle_at: str | None = None
        self._cycle_lock = Lock()
        self._restore_state()

    def run_cycle(self) -> dict[str, int | str]:
        if not self._cycle_lock.acquire(blocking=False):
            return {"status": "already_running", "opened": 0}
        try:
            return self._run_cycle()
        finally:
            self._cycle_lock.release()

    def _run_cycle(self) -> dict[str, int | str]:
        settings = self._settings_service.get_settings_state()
        self._last_cycle_at = datetime.now(timezone.utc).isoformat()
        self._last_candidate_signal = None
        self._last_order = None
        self._last_reject_reason = None
        self._last_scanner_status = "idle"
        self._last_signal_status = "idle"
        self._last_execution_status = "idle"

        try:
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

            persistence_ready, persistence_reason = self._execution_persistence_ready()
            if not persistence_ready:
                self._settings_service.update_control_state({"auto_trade_enabled": False})
                self._last_execution_status = "blocked"
                self._last_reject_reason = persistence_reason
                return {"status": "database_not_ready", "opened": 0}

            bybit_status = self._bybit_service.get_connection_status().data
            if bybit_status.code != "CONNECTED":
                self._last_execution_status = "blocked"
                self._last_reject_reason = bybit_status.detail
                return {"status": "exchange_disconnected", "opened": 0}

            self._trade_service.sync_with_exchange(self._bybit_service)

            if self._trade_service.get_daily_trade_count() >= settings.daily_max_trades:
                self._last_execution_status = "blocked"
                self._last_reject_reason = (
                    f"Daily trade limit of {settings.daily_max_trades} reached."
                )
                return {"status": "daily_trade_stop", "opened": 0}

            if (
                self._trade_service.get_remaining_daily_loss_budget(
                    settings.daily_max_loss
                )
                <= 0
            ):
                self._settings_service.update_control_state(
                    {"auto_trade_enabled": False}
                )
                self._last_execution_status = "blocked"
                self._last_reject_reason = "Daily max loss limit reached."
                return {"status": "daily_loss_stop", "opened": 0}

            blocked_modes, combined_stop = self._realized_loss_blocks()
            if combined_stop:
                self._settings_service.update_control_state({"auto_trade_enabled": False})
                self._last_execution_status = "blocked"
                self._last_reject_reason = (
                    "Combined net realized daily loss reached -5%. Auto trade stopped."
                )
                return {"status": "realized_loss_stop", "opened": 0}

            active_data = self._trade_service.get_active_trades().data
            if (
                len(active_data.scalping_trades) + len(active_data.intraday_trades)
                >= COMBINED_MAX_OPEN_TRADES
            ):
                self._last_execution_status = "blocked"
                self._last_reject_reason = (
                    f"Combined open-position limit of {COMBINED_MAX_OPEN_TRADES} reached."
                )
                return {"status": "open_position_stop", "opened": 0}

            open_counts = {
                TradingMode.SCALPING: len(active_data.scalping_trades),
                TradingMode.INTRADAY: len(active_data.intraday_trades),
            }
            opened_by_mode = {
                TradingMode.SCALPING: 0,
                TradingMode.INTRADAY: 0,
            }

            enabled_modes: list[TradingMode] = []
            if settings.scalping_engine_enabled and TradingMode.SCALPING not in blocked_modes:
                enabled_modes.append(TradingMode.SCALPING)
            if settings.intraday_engine_enabled and TradingMode.INTRADAY not in blocked_modes:
                enabled_modes.append(TradingMode.INTRADAY)

            if not enabled_modes:
                self._last_execution_status = "blocked"
                self._last_reject_reason = "All enabled modes reached their net realized loss limits."
                return {"status": "realized_loss_stop", "opened": 0}

            opened = 0
            scanned_symbols = 0
            evaluated_count = 0

            for mode in enabled_modes:
                timeframe = self._strategy_service.default_timeframe(mode)
                symbols = self._strategy_service.default_symbols(mode)
                scanned_symbols += len(symbols)
                evaluated_signals = []
                mode_limit = self.MODE_OPEN_LIMITS[mode]

                for symbol in symbols:
                    try:
                        signal = self._strategy_service.evaluate_symbol(
                            symbol=symbol,
                            mode=mode,
                            timeframe=timeframe,
                        )
                    except HTTPException as exc:
                        self._last_reject_reason = self._format_http_detail(exc.detail)
                        continue

                    if signal is None:
                        continue
                    evaluated_signals.append(signal)
                    evaluated_count += 1

                    if open_counts[mode] + opened_by_mode[mode] >= mode_limit:
                        self._last_reject_reason = (
                            f"{mode.value.title()} open-trade limit of {mode_limit} reached."
                        )
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

                    try:
                        leverage_setter = getattr(self._bybit_service, "set_symbol_leverage", None)
                        if callable(leverage_setter):
                            leverage_setter(signal.symbol, self.MODE_LEVERAGE[mode])
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
                    opened_by_mode[mode] += 1

                self._signal_registry.replace(
                    mode,
                    evaluated_signals,
                    source="auto_trade_cycle",
                )

            self._last_scanner_status = (
                f"scanned_{scanned_symbols}_symbols_across_{len(enabled_modes)}_modes"
            )

            if evaluated_count == 0:
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

    def _realized_loss_blocks(self) -> tuple[set[TradingMode], bool]:
        if self._profit_tracking_service is None:
            return set(), False
        state = self._profit_tracking_service.refresh_from_sources(
            self._trade_service,
            self._bybit_service,
        )
        baseline = state.daily_start_equity
        if baseline is None or baseline <= 0:
            return set(), False

        today = trading_date()
        closed = self._trade_service.get_closed_trades().data.closed_trades
        realized_by_mode = {
            TradingMode.SCALPING: 0.0,
            TradingMode.INTRADAY: 0.0,
        }
        for trade in closed:
            if not is_on_trading_date(trade.closed_time, today):
                continue
            mode = trade.mode
            if mode in realized_by_mode:
                realized_by_mode[mode] += float(trade.realized_pnl or 0.0)

        blocked_modes = {
            mode
            for mode, realized in realized_by_mode.items()
            if (realized / baseline) * 100.0 <= self.MODE_REALIZED_LOSS_LIMIT_PCT[mode]
        }
        combined_stop = state.daily_realized_pct <= self.COMBINED_REALIZED_LOSS_LIMIT_PCT
        return blocked_modes, combined_stop

    def _execution_persistence_ready(self) -> tuple[bool, str | None]:
        if self._repository is None:
            return True, None

        checker = getattr(self._repository, "verify_execution_ready", None)
        if not callable(checker):
            return True, None

        ready, reason = checker()
        if ready:
            return True, None
        return (
            False,
            "PostgreSQL persistence is required before auto trade can run: "
            f"{reason}",
        )

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
