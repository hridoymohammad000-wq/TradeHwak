import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.core.config import get_app_config
from app.core.exceptions import register_exception_handlers
from app.core.state import (
    auto_trade_service,
    bybit_service,
    persistence_repository,
    profit_tracking_service,
    settings_service,
    trade_management_service,
    trade_service,
)

SCANNER_INTERVAL_SECONDS = 300
TRADE_MANAGEMENT_INTERVAL_SECONDS = 15
EXCHANGE_RECONCILIATION_INTERVAL_SECONDS = 30
AUTO_TRADE_WORKER_LOCK = "tradehawk:worker:auto_trade"
TRADE_MANAGEMENT_WORKER_LOCK = "tradehawk:worker:trade_management"
EXCHANGE_RECONCILIATION_WORKER_LOCK = "tradehawk:worker:exchange_reconciliation"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = REPOSITORY_ROOT / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"


def _run_with_worker_leader_lock(lock_name: str, operation):
    session = getattr(persistence_repository, "advisory_lock_session", None)
    if callable(session):
        with session(lock_name) as acquired:
            if not acquired:
                return {"status": "leader_not_acquired"}
            return operation()

    locker = getattr(persistence_repository, "try_advisory_lock", None)
    unlocker = getattr(persistence_repository, "advisory_unlock", None)
    if not callable(locker) or not callable(unlocker):
        return operation()
    acquired = locker(lock_name)
    if not acquired:
        return {"status": "leader_not_acquired"}
    try:
        return operation()
    finally:
        unlocker(lock_name)


async def _run_logged_worker(
    *,
    event_type: str,
    failure_event_type: str,
    leader_lock_name: str,
    operation,
    sleep_seconds: int,
) -> None:
    while True:
        try:
            result = await asyncio.to_thread(
                _run_with_worker_leader_lock,
                leader_lock_name,
                operation,
            )
            persistence_repository.append_log("execution_logs", event_type, result)
        except Exception as exc:
            persistence_repository.append_log(
                "execution_logs",
                failure_event_type,
                {"error": str(exc)},
            )
        await asyncio.sleep(sleep_seconds)


async def _auto_trade_loop() -> None:
    await _run_logged_worker(
        event_type="auto_trade_cycle",
        failure_event_type="auto_trade_cycle_failed",
        leader_lock_name=AUTO_TRADE_WORKER_LOCK,
        operation=auto_trade_service.run_cycle,
        sleep_seconds=SCANNER_INTERVAL_SECONDS,
    )


async def _trade_management_loop() -> None:
    await _run_logged_worker(
        event_type="trade_management_cycle",
        failure_event_type="trade_management_cycle_failed",
        leader_lock_name=TRADE_MANAGEMENT_WORKER_LOCK,
        operation=trade_management_service.manage_open_trades,
        sleep_seconds=TRADE_MANAGEMENT_INTERVAL_SECONDS,
    )


def _reconcile_exchange_state() -> dict[str, int | str]:
    trade_service.sync_with_exchange(bybit_service)
    active = trade_service.get_active_trades().data
    return {
        "status": "reconciled",
        "total_open_trades": len(active.scalping_trades) + len(active.intraday_trades),
    }


async def _exchange_reconciliation_loop() -> None:
    await _run_logged_worker(
        event_type="exchange_reconciliation_cycle",
        failure_event_type="exchange_reconciliation_cycle_failed",
        leader_lock_name=EXCHANGE_RECONCILIATION_WORKER_LOCK,
        operation=_reconcile_exchange_state,
        sleep_seconds=EXCHANGE_RECONCILIATION_INTERVAL_SECONDS,
    )


def _initialize_runtime_state() -> None:
    if persistence_repository.database_url:
        initialized = persistence_repository.initialize()
        if not initialized:
            raise RuntimeError(
                persistence_repository.last_error
                or "Database initialization failed."
            )
        ready, reason = persistence_repository.verify_execution_ready()
        if not ready:
            raise RuntimeError(reason or "Database readiness verification failed.")
    settings_service.reload_from_persistence()
    trade_service.reload_from_persistence()
    profit_tracking_service.reload_from_persistence()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _initialize_runtime_state()
    bybit_service.start_websockets()
    tasks = [
        asyncio.create_task(_auto_trade_loop()),
        asyncio.create_task(_trade_management_loop()),
        asyncio.create_task(_exchange_reconciliation_loop()),
    ]
    try:
        yield
    finally:
        bybit_service.stop_websockets()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


config = get_app_config()

app = FastAPI(
    title=config.app_name,
    version=config.version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
# Render health checks and same-origin frontend authentication endpoints.
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(api_router, prefix="/api")
# Temporary compatibility prefix for older frontend bundles that sent /api/api/*.
app.include_router(api_router, prefix="/api/api", include_in_schema=False)

if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str) -> FileResponse:
    """Serve the built React SPA without intercepting backend/API paths."""
    protected_prefixes = ("api", "auth", "health")
    if full_path == "api" or full_path.startswith(tuple(f"{prefix}/" for prefix in protected_prefixes)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

    requested_file = FRONTEND_DIST / full_path
    if full_path and requested_file.is_file() and FRONTEND_DIST in requested_file.resolve().parents:
        return FileResponse(requested_file)
    if FRONTEND_INDEX.is_file():
        return FileResponse(FRONTEND_INDEX)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Frontend build is unavailable.",
    )
