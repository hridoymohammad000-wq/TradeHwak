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
    persistence_repository,
    profit_tracking_service,
    settings_service,
    trade_service,
)
from app.services.exchange_reconciliation import install_exchange_reconciliation_patch


install_exchange_reconciliation_patch()

AUTO_TRADE_INTERVAL_SECONDS = 300
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = REPOSITORY_ROOT / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"


async def _auto_trade_loop() -> None:
    while True:
        try:
            result = auto_trade_service.run_cycle()
            persistence_repository.append_log("execution_logs", "auto_trade_cycle", result)
        except Exception as exc:
            persistence_repository.append_log(
                "execution_logs",
                "auto_trade_cycle_failed",
                {"error": str(exc)},
            )
        await asyncio.sleep(AUTO_TRADE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    persistence_repository.initialize()
    settings_service.reload_from_persistence()
    trade_service.reload_from_persistence()
    profit_tracking_service.reload_from_persistence()
    task = asyncio.create_task(_auto_trade_loop())
    try:
        yield
    finally:
        task.cancel()
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
