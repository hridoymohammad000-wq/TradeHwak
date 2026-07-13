from app.core.config import get_app_config
from app.db.repository import PersistenceRepository
from app.double_down.persistence import ChallengePersistence
from app.double_down.service import ChallengeService
from app.services.chart_context_service import ChartContextService
from app.services.dashboard_service import DashboardService
from app.services.engine_service import EngineService
from app.services.managed_auto_trade_service import ManagedAutoTradeService
from app.services.managed_bybit_service import ManagedBybitService
from app.services.managed_manual_trade_service import ManagedManualTradeService
from app.services.managed_strategy_service import ManagedStrategyService
from app.services.profit_tracking_service import ProfitTrackingService
from app.services.risk_execution_guard import RiskExecutionGuard
from app.services.scanner_service import ScannerService
from app.services.settings_service import SettingsService
from app.services.signal_registry import SignalRegistry
from app.services.signals_service import SignalsService
from app.services.runtime_health_service import RuntimeHealthService
from app.services.system_service import SystemService
from app.services.trade_management_service import TradeManagementService
from app.services.trade_service import TradeService


persistence_repository = PersistenceRepository(get_app_config().database_url)
runtime_health_service = RuntimeHealthService()
challenge_persistence = ChallengePersistence(persistence_repository)
settings_service = SettingsService(repository=persistence_repository)
bybit_service = ManagedBybitService()
system_service = SystemService(
    settings_service=settings_service,
    repository=persistence_repository,
    bybit_service=bybit_service,
    runtime_health_service=runtime_health_service,
)
challenge_service = ChallengeService(challenge_persistence, bybit_service=bybit_service)
strategy_service = ManagedStrategyService(bybit_service=bybit_service)
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
profit_tracking_service = ProfitTrackingService(repository=persistence_repository)
risk_execution_guard = RiskExecutionGuard()
manual_trade_service = ManagedManualTradeService(
    settings_service=settings_service,
    bybit_service=bybit_service,
    trade_service=trade_service,
    repository=persistence_repository,
    profit_tracking_service=profit_tracking_service,
    risk_execution_guard=risk_execution_guard,
)
trade_management_service = TradeManagementService(
    bybit_service=bybit_service,
    trade_service=trade_service,
    repository=persistence_repository,
)
auto_trade_service = ManagedAutoTradeService(
    settings_service=settings_service,
    bybit_service=bybit_service,
    strategy_service=strategy_service,
    manual_trade_service=manual_trade_service,
    trade_service=trade_service,
    signal_registry=signal_registry,
    repository=persistence_repository,
    profit_tracking_service=profit_tracking_service,
    trade_management_service=trade_management_service,
)
dashboard_service = DashboardService(
    settings_service=settings_service,
    trade_service=trade_service,
    bybit_service=bybit_service,
    profit_tracking_service=profit_tracking_service,
)
chart_context_service = ChartContextService(bybit_service=bybit_service)
engine_service = EngineService(
    settings_service=settings_service,
    bybit_service=bybit_service,
    repository=persistence_repository,
)
