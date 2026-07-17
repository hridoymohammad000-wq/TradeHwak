from functools import lru_cache
from os import getenv
from pathlib import Path
import os

from pydantic import BaseModel

from app.core.enums import RuntimeMode, TradingMode


def _load_local_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env_file()


def _parse_cors_origins(*origin_values: str, include_local_origins: bool) -> list[str]:
    local_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    configured_origins = [
        origin.strip().rstrip("/")
        for value in origin_values
        for origin in value.split(",")
        if origin.strip()
    ]
    origins = [*configured_origins]
    if include_local_origins:
        origins = [*local_origins, *origins]
    return list(dict.fromkeys(origins))


def _read_port() -> int:
    raw_port = getenv("PORT") or getenv("APP_PORT") or "8000"
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(f'PORT must be a valid integer, received "{raw_port}".') from exc

    if port <= 0:
        raise ValueError("PORT must be greater than zero.")
    return port


def _read_bool(name: str, default: bool = False) -> bool:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f'{name} must be a valid integer, received "{raw_value}".') from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return value


class AppConfig(BaseModel):
    app_name: str = "TradeHawk Backend"
    version: str = "0.3.0"
    phase: str = "operational"
    execution_enabled: bool = False
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_url: str = "http://localhost:5173"
    cors_origins_env: str = ""
    database_url: str = ""
    database_pool_min_size: int = 1
    database_pool_max_size: int = 5
    log_retention_days: int = 14
    default_system_mode: RuntimeMode = RuntimeMode.DEMO
    default_strategy_mode: TradingMode = TradingMode.INTRADAY

    @property
    def cors_origins(self) -> list[str]:
        include_local_origins = self.app_env.strip().lower() != "production"
        return _parse_cors_origins(
            self.frontend_url,
            self.cors_origins_env,
            include_local_origins=include_local_origins,
        )


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    return AppConfig(
        app_name=getenv("APP_NAME", "TradeHawk Backend"),
        version=getenv("APP_VERSION", "0.3.0"),
        phase=getenv("APP_PHASE", "operational"),
        execution_enabled=_read_bool("EXECUTION_ENABLED", False),
        app_env=getenv("APP_ENV", "development"),
        app_host=getenv("APP_HOST", "127.0.0.1"),
        app_port=_read_port(),
        frontend_url=getenv("FRONTEND_URL", "http://localhost:5173"),
        cors_origins_env=getenv("CORS_ORIGINS", ""),
        database_url=getenv("DATABASE_URL", ""),
        database_pool_min_size=_read_int("DATABASE_POOL_MIN_SIZE", 1, minimum=0),
        database_pool_max_size=_read_int("DATABASE_POOL_MAX_SIZE", 5, minimum=1),
        log_retention_days=_read_int("LOG_RETENTION_DAYS", 14, minimum=1),
        default_system_mode=RuntimeMode(getenv("DEFAULT_SYSTEM_MODE", "demo")),
        default_strategy_mode=TradingMode(
            getenv("DEFAULT_STRATEGY_MODE", "intraday")
        ),
    )
