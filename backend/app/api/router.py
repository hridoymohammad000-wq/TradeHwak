from fastapi import APIRouter, Depends

from app.api.dependencies import require_authenticated_session
from app.api.routes.auth import router as auth_router
from app.api.routes.bybit import router as bybit_router
from app.api.routes.chart_context import router as chart_context_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.engine_control import router as engine_control_router
from app.api.routes.health import router as health_router
from app.api.routes.mode import router as mode_router
from app.api.routes.performance import router as performance_router
from app.api.routes.scanner import router as scanner_router
from app.api.routes.settings import router as settings_router
from app.api.routes.signals import router as signals_router
from app.api.routes.trades import router as trades_router
from app.api.routes.workflow import router as workflow_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)

protected_router = APIRouter(dependencies=[Depends(require_authenticated_session)])
protected_router.include_router(mode_router)
protected_router.include_router(bybit_router)
protected_router.include_router(dashboard_router)
protected_router.include_router(settings_router)
protected_router.include_router(scanner_router)
protected_router.include_router(signals_router)
protected_router.include_router(trades_router)
protected_router.include_router(performance_router)
protected_router.include_router(chart_context_router)
protected_router.include_router(engine_control_router)
protected_router.include_router(workflow_router)
api_router.include_router(protected_router)
