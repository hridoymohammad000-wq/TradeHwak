import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.core.config import get_app_config
from app.core.exceptions import register_exception_handlers
from app.core.state import (
    auto_trade_service,
    persistence_repository,
    settings_service,
    trade_service,
)


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
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(_: FastAPI):
    persistence_repository.initialize()
    settings_service.reload_from_persistence()
    trade_service.reload_from_persistence()
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
# Render health checks and the existing frontend auth calls remain available at root.
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(api_router, prefix="/api")
