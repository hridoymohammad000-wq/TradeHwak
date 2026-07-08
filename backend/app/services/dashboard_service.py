from datetime import datetime

from fastapi import HTTPException

from app.core.enums import SystemStatus
from app.schemas.dashboard import (
    DashboardAccountSummary,
    DashboardEvent,
    DashboardSummaryData,
    DashboardSummaryResponse,
    DashboardTodaySummary,
)
from app.services.bybit_service import BybitService
from app.services.settings_service import SettingsService
from app.services.trade_service import TradeService
from app.services.runtime_store import RuntimeStore


class DashboardService:
    def __init__(
        self,
        settings_service: SettingsService,
        trade_service: TradeService,
        runtime_store: RuntimeStore,
        bybit_service: BybitService,
    ) -> None:
        self._settings_service = settings_service
        self._trade_service = trade_service
        self._runtime_store = runtime_store
        self._bybit_service = bybit_service

    def get_summary(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> DashboardSummaryResponse:
        settings = self._settings_service.get_settings_state()
        self._trade_service.sync_with_exchange(self._bybit_service)
        active_data = self._trade_service.get_active_trades(
            start_time=start_time,
            end_time=end_time,
        ).data
        closed_data = self._trade_service.get_closed_trades(
            start_time=start_time,
            end_time=end_time,
        ).data
        combined = closed_data.summaries.combined
        recent_events = [
            DashboardEvent.model_validate(event)
            for event in self._runtime_store.get_events(limit=8)
        ]
        active_pnls = [trade.pnl for trade in active_data.active_trades]
        unrealized_pnl = (
            round(sum(float(value) for value in active_pnls), 8)
            if active_pnls and all(value is not None for value in active_pnls)
            else None
        )

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
                account=self._get_account_summary(),
                today_summary=DashboardTodaySummary(
                    total_open_trades=active_data.today_summary.total_open_trades,
                    scalping_open_trades=active_data.today_summary.scalping_open_trades,
                    intraday_open_trades=active_data.today_summary.intraday_open_trades,
                    unknown_open_trades=active_data.today_summary.unknown_open_trades,
                    closed_trades_today=combined.total_trades,
                    wins_today=combined.wins,
                    losses_today=combined.losses,
                    win_rate_today=combined.win_rate,
                    unrealized_pnl=unrealized_pnl,
                    realized_pnl_today=combined.realized_pnl,
                    average_risk_reward_today=combined.average_risk_reward,
                ),
                recent_events=recent_events,
                range_start=active_data.range_start,
                range_end=active_data.range_end,
            ),
        )

    def _get_account_summary(self) -> DashboardAccountSummary:
        config_status = self._bybit_service.get_config_status().data
        if not config_status.configured:
            return DashboardAccountSummary(status="not_configured")
        try:
            wallet = self._bybit_service.get_wallet_snapshot()
        except HTTPException:
            return DashboardAccountSummary(status="unavailable")
        return DashboardAccountSummary(
            status="connected",
            equity=float(wallet["equity"]),
            available_balance=float(wallet["available"]),
        )
