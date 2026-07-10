from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.enums import SystemStatus, TradingMode
from app.schemas.dashboard import (
    DashboardAccount,
    DashboardEvent,
    DashboardSummaryData,
    DashboardSummaryResponse,
    DashboardTodaySummary,
)
from app.services.bybit_service import BybitService
from app.services.settings_service import SettingsService
from app.services.trade_service import TradeService


class DashboardService:
    def __init__(
        self,
        settings_service: SettingsService,
        trade_service: TradeService,
        bybit_service: BybitService,
    ) -> None:
        self._settings_service = settings_service
        self._trade_service = trade_service
        self._bybit_service = bybit_service

    @staticmethod
    def _today_prefix() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def get_summary(self) -> DashboardSummaryResponse:
        settings = self._settings_service.get_settings_state()
        self._trade_service.sync_with_exchange(self._bybit_service)
        active_data = self._trade_service.get_active_trades().data
        closed_records = self._trade_service.get_closed_trades().data.closed_trades

        active_records = [*active_data.scalping_trades, *active_data.intraday_trades]
        scalping_open = sum(1 for trade in active_records if trade.mode == TradingMode.SCALPING)
        intraday_open = sum(1 for trade in active_records if trade.mode == TradingMode.INTRADAY)
        unknown_open = max(len(active_records) - scalping_open - intraday_open, 0)
        unrealized_values = [trade.pnl for trade in active_records if trade.pnl is not None]
        unrealized_pnl = sum(unrealized_values) if unrealized_values else None

        today_prefix = self._today_prefix()
        closed_today = [
            trade for trade in closed_records
            if (trade.closed_time or "").startswith(today_prefix)
        ]
        wins = sum(1 for trade in closed_today if trade.result == "win")
        losses = sum(1 for trade in closed_today if trade.result == "loss")
        realized_values = [trade.realized_pnl for trade in closed_today if trade.realized_pnl is not None]
        rr_values = [trade.risk_reward for trade in closed_today if trade.risk_reward is not None]

        account = DashboardAccount(status="unavailable")
        try:
            wallet = self._bybit_service.get_wallet_snapshot()
            account = DashboardAccount(
                status="connected",
                equity=float(wallet["equity"]),
                available_balance=float(wallet["available"]),
            )
        except (HTTPException, KeyError, TypeError, ValueError):
            pass

        now = datetime.now(timezone.utc).isoformat()
        recent_events = [
            DashboardEvent(
                event_type="exchange_state",
                message=f"Bybit Demo account is {account.status}.",
                created_at=now,
            ),
            DashboardEvent(
                event_type="engine_state",
                message=(
                    "Scalping engine is "
                    + ("enabled" if settings.scalping_engine_enabled else "disabled")
                    + "; intraday engine is "
                    + ("enabled" if settings.intraday_engine_enabled else "disabled")
                    + "."
                ),
                created_at=now,
            ),
            DashboardEvent(
                event_type="risk_guard",
                message=(
                    "Auto trade is "
                    + ("armed" if settings.auto_trade_enabled else "locked")
                    + " and emergency stop is "
                    + ("active." if settings.emergency_stop else "clear.")
                ),
                created_at=now,
            ),
        ]

        return DashboardSummaryResponse(
            message="Dashboard summary fetched successfully.",
            data=DashboardSummaryData(
                system_status=SystemStatus.PENDING_INTEGRATION,
                system_mode=settings.system_mode,
                active_strategy_mode=settings.active_strategy_mode,
                scalping_engine_enabled=settings.scalping_engine_enabled,
                intraday_engine_enabled=settings.intraday_engine_enabled,
                auto_trade_enabled=settings.auto_trade_enabled,
                emergency_stop=settings.emergency_stop,
                account=account,
                today_summary=DashboardTodaySummary(
                    total_open_trades=len(active_records),
                    scalping_open_trades=scalping_open,
                    intraday_open_trades=intraday_open,
                    unknown_open_trades=unknown_open,
                    closed_trades_today=len(closed_today),
                    wins_today=wins,
                    losses_today=losses,
                    win_rate_today=(wins / len(closed_today) * 100) if closed_today else None,
                    unrealized_pnl=unrealized_pnl,
                    realized_pnl_today=sum(realized_values) if realized_values else None,
                    average_risk_reward_today=(sum(rr_values) / len(rr_values)) if rr_values else None,
                ),
                recent_events=recent_events,
            ),
        )
