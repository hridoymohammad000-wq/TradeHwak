from app.services.auth_service import AuthService
from app.services.auto_trade_service import AutoTradeService
from app.services.bybit_service import BybitService
from app.services.dashboard_service import DashboardService
from app.services.chart_context_service import ChartContextService
from app.services.engine_service import EngineService
from app.services.manual_trade_service import ManualTradeService
from app.services.performance_service import PerformanceService
from app.services.runtime_store import RuntimeStore
from app.services.scanner_service import ScannerService
from app.services.settings_service import SettingsService
from app.services.signals_service import SignalsService
from app.services.strategy_service import StrategyService
from app.services.system_service import SystemService
from app.services.trade_service import TradeService


from app.core.config import get_app_config


auth_service = AuthService(get_app_config())
runtime_store = RuntimeStore(get_app_config())
settings_service = SettingsService(runtime_store=runtime_store)
system_service = SystemService()
bybit_service = BybitService()
strategy_service = StrategyService(bybit_service=bybit_service)
scanner_service = ScannerService(
    settings_service=settings_service,
    strategy_service=strategy_service,
)
signals_service = SignalsService(
    settings_service=settings_service,
    strategy_service=strategy_service,
)
trade_service = TradeService(
    settings_service=settings_service,
    runtime_store=runtime_store,
)
manual_trade_service = ManualTradeService(
    settings_service=settings_service,
    bybit_service=bybit_service,
    trade_service=trade_service,
)
auto_trade_service = AutoTradeService(
    settings_service=settings_service,
    bybit_service=bybit_service,
    strategy_service=strategy_service,
    manual_trade_service=manual_trade_service,
    trade_service=trade_service,
    runtime_store=runtime_store,
)
dashboard_service = DashboardService(
    settings_service=settings_service,
    trade_service=trade_service,
    runtime_store=runtime_store,
    bybit_service=bybit_service,
)
performance_service = PerformanceService(trade_service=trade_service)
chart_context_service = ChartContextService(bybit_service=bybit_service)
engine_service = EngineService(
    settings_service=settings_service,
    bybit_service=bybit_service,
)

if not runtime_store.get_events(limit=1):
    runtime_store.append_event(
        "backend_boot",
        f"Runtime state initialized using {runtime_store.storage_mode} storage.",
    )
elif runtime_store.last_remote_error:
    runtime_store.append_event(
        "storage_warning",
        f"Supabase sync fallback active: {runtime_store.last_remote_error}",
    )
