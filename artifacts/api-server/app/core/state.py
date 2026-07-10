from app.core.config import get_app_config
from app.db.repository import PersistenceRepository
from app.services.bybit_service import BybitService
from app.services.dashboard_service import DashboardService
from app.services.chart_context_service import ChartContextService
from app.services.engine_service import EngineService
from app.services.managed_auto_trade_service import ManagedAutoTradeService
from app.services.manual_trade_service import ManualTradeService
from app.services.scanner_service import ScannerService
from app.services.settings_service import SettingsService
from app.services.signal_registry import SignalRegistry
from app.services.signals_service import SignalsService
from app.services.strategy_service import StrategyService
from app.services.system_service import SystemService
from app.services.trade_service import TradeService
from app.services.trailing_stop_service import TrailingStopService


persistence_repository = PersistenceRepository(get_app_config().database_url)
settings_service = SettingsService(repository=persistence_repository)
system_service = SystemService(settings_service=settings_service)
bybit_service = BybitService()
strategy_service = StrategyService(bybit_service=bybit_service)
signal_registry = SignalRegistry(repository=persistence_repository)
scanner_service = ScannerService(
    settings_service=settings_service,
    strategy_service=strategy_service,
    signal_registry=signal_registry,
)
signals_service = SignalsService(
    settings_service=settings_service,
    strategy_service=strategy_service,
    signal_registry=signal_registry,
)
trade_service = TradeService(
    settings_service=settings_service,
    repository=persistence_repository,
)
manual_trade_service = ManualTradeService(
    settings_service=settings_service,
    bybit_service=bybit_service,
    trade_service=trade_service,
    repository=persistence_repository,
)
trailing_stop_service = TrailingStopService(
    bybit_service=bybit_service,
    trade_service=trade_service,
)
auto_trade_service = ManagedAutoTradeService(
    settings_service=settings_service,
    bybit_service=bybit_service,
    strategy_service=strategy_service,
    manual_trade_service=manual_trade_service,
    trade_service=trade_service,
    signal_registry=signal_registry,
    repository=persistence_repository,
    trailing_stop_service=trailing_stop_service,
)
dashboard_service = DashboardService(
    settings_service=settings_service,
    trade_service=trade_service,
    bybit_service=bybit_service,
)
chart_context_service = ChartContextService()
engine_service = EngineService(
    settings_service=settings_service,
    bybit_service=bybit_service,
)
