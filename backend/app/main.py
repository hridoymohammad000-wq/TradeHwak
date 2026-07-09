import asyncio
from contextlib import asynccontextmanager, suppress
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_app_config, validate_startup_environment


config = get_app_config()
startup_environment_messages = validate_startup_environment()

# Import route/state wiring only after the security-critical environment validation.
from app.api.router import api_router  # noqa: E402
from app.core.exceptions import register_exception_handlers  # noqa: E402
from app.core.state import auto_trade_service  # noqa: E402


logger = logging.getLogger("uvicorn.error")


async def _auto_trade_loop() -> None:
    while True:
        try:
            auto_trade_service.run_cycle()
        except Exception:
            logger.exception("Auto-trade background cycle failed.")
        await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(_: FastAPI):
    for message in startup_environment_messages:
        logger.info(message)

    task = asyncio.create_task(_auto_trade_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title=config.app_name,
    version=config.version,
    docs_url="/docs",
    redoc_url="/redoc",
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
app.include_router(api_router)
