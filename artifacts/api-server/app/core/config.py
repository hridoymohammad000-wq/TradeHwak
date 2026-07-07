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


def _parse_cors_origins(*origin_values: str) -> list[str]:
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
    return list(dict.fromkeys([*local_origins, *configured_origins]))


def _read_port() -> int:
    raw_port = getenv("PORT") or getenv("APP_PORT") or "8000"
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(f'PORT must be a valid integer, received "{raw_port}".') from exc

    if port <= 0:
        raise ValueError("PORT must be greater than zero.")
    return port


class AppConfig(BaseModel):
    app_name: str = "Crypto Scalping Trader Backend"
    version: str = "0.2.0"
    phase: str = "foundation"
    execution_enabled: bool = False
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_url: str = "http://localhost:5173"
    cors_origins_env: str = ""
    database_url: str = ""
    default_system_mode: RuntimeMode = RuntimeMode.DEMO
    default_strategy_mode: TradingMode = TradingMode.SCALPING

    @property
    def cors_origins(self) -> list[str]:
        return _parse_cors_origins(self.frontend_url, self.cors_origins_env)


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    return AppConfig(
        app_name=getenv("APP_NAME", "Crypto Scalping Trader Backend"),
        app_env=getenv("APP_ENV", "development"),
        app_host=getenv("APP_HOST", "127.0.0.1"),
        app_port=_read_port(),
        frontend_url=getenv("FRONTEND_URL", "http://localhost:5173"),
        cors_origins_env=getenv("CORS_ORIGINS", ""),
        database_url=getenv("DATABASE_URL", ""),
        default_system_mode=RuntimeMode(getenv("DEFAULT_SYSTEM_MODE", "demo")),
        default_strategy_mode=TradingMode(
            getenv("DEFAULT_STRATEGY_MODE", "scalping")
        ),
    )
