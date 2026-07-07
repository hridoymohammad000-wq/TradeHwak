from app.core.enums import SystemStatus
from app.schemas.dashboard import (
    DashboardEvent,
    DashboardSummaryData,
    DashboardSummaryResponse,
    DashboardTodaySummary,
)
from app.services.settings_service import SettingsService
from app.services.trade_service import TradeService


class DashboardService:
    def __init__(
        self,
        settings_service: SettingsService,
        trade_service: TradeService,
    ) -> None:
        self._settings_service = settings_service
        self._trade_service = trade_service

    def get_summary(self) -> DashboardSummaryResponse:
        settings = self._settings_service.get_settings_state()
        active_trades = self._trade_service.get_active_trades().data
        recent_events = [
            DashboardEvent(
                event_type="boot",
                message="Local preview mode is active. Mock execution state loaded for frontend integration.",
                created_at="2026-07-06 10:30",
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
                created_at="2026-07-06 10:32",
            ),
            DashboardEvent(
                event_type="risk_guard",
                message=(
                    "Auto trade is "
                    + ("armed" if settings.auto_trade_enabled else "locked")
                    + " and emergency stop is "
                    + ("active." if settings.emergency_stop else "clear.")
                ),
                created_at="2026-07-06 10:34",
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
                today_summary=DashboardTodaySummary(
                    total_open_trades=active_trades.today_summary.total_open_trades,
                    closed_trades_today=active_trades.today_summary.closed_trades_today,
                ),
                recent_events=recent_events,
            ),
        )
