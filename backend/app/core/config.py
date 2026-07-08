from functools import lru_cache
from os import getenv
from pathlib import Path
import os

from pydantic import BaseModel, SecretStr

from app.core.enums import RuntimeMode, TradingMode


BYBIT_DEMO_BASE_URL = "https://api-demo.bybit.com"
BYBIT_PRIVATE_ENV_VARS = ("BYBIT_DEMO_API_KEY", "BYBIT_DEMO_API_SECRET")
SUPABASE_PRIVATE_ENV_VARS = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
FORBIDDEN_FRONTEND_SECRET_VARS = (
    "VITE_BYBIT_DEMO_API_KEY",
    "VITE_BYBIT_DEMO_API_SECRET",
    "VITE_SUPABASE_SERVICE_ROLE_KEY",
    "VITE_TRADEHAWK_ACCESS_TOKEN",
    "VITE_ACCESS_TOKEN",
)
SESSION_COOKIE_SAMESITE_VALUES = {"lax", "strict", "none"}


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


def _parse_frontend_origins(frontend_url: str) -> list[str]:
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    configured = [origin.strip().rstrip("/") for origin in frontend_url.split(",") if origin.strip()]
    return list(dict.fromkeys([*defaults, *configured]))


def _configured(name: str) -> bool:
    return bool((getenv(name) or "").strip())


def _parse_bool(name: str, default: bool) -> bool:
    raw_value = getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be true or false.")


def _parse_positive_int(name: str, default: int, maximum: int) -> int:
    raw_value = (getenv(name) or str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if value <= 0 or value > maximum:
        raise RuntimeError(f"{name} must be between 1 and {maximum}.")
    return value


def validate_startup_environment() -> list[str]:
    """Validate backend-only environment configuration without exposing values."""
    bybit_env = (getenv("BYBIT_ENV") or "demo").strip().lower()
    bybit_base_url = (getenv("BYBIT_BASE_URL") or BYBIT_DEMO_BASE_URL).strip().rstrip("/")

    if bybit_env != "demo" or bybit_base_url != BYBIT_DEMO_BASE_URL:
        raise RuntimeError(
            "Unsafe Bybit configuration blocked. TradeHawk requires BYBIT_ENV=demo "
            f"and BYBIT_BASE_URL={BYBIT_DEMO_BASE_URL}."
        )

    exposed_names = [name for name in FORBIDDEN_FRONTEND_SECRET_VARS if _configured(name)]
    if exposed_names:
        raise RuntimeError(
            "Backend secrets must not use frontend-exposed VITE_* variables: "
            + ", ".join(exposed_names)
        )

    access_token = (getenv("TRADEHAWK_ACCESS_TOKEN") or "").strip()
    if not access_token:
        raise RuntimeError(
            "TRADEHAWK_ACCESS_TOKEN is required for private TradeHawk access."
        )
    if len(access_token) < 32:
        raise RuntimeError(
            "TRADEHAWK_ACCESS_TOKEN must contain at least 32 characters."
        )

    session_ttl_minutes = _parse_positive_int(
        "TRADEHAWK_SESSION_TTL_MINUTES", default=480, maximum=1440
    )
    app_env = (getenv("APP_ENV") or "development").strip().lower()
    session_cookie_secure = _parse_bool(
        "TRADEHAWK_SESSION_COOKIE_SECURE", default=app_env not in {"development", "test"}
    )
    session_cookie_samesite = (
        getenv("TRADEHAWK_SESSION_COOKIE_SAMESITE") or "lax"
    ).strip().lower()
    if session_cookie_samesite not in SESSION_COOKIE_SAMESITE_VALUES:
        raise RuntimeError(
            "TRADEHAWK_SESSION_COOKIE_SAMESITE must be lax, strict, or none."
        )
    if session_cookie_samesite == "none" and not session_cookie_secure:
        raise RuntimeError(
            "TRADEHAWK_SESSION_COOKIE_SECURE must be true when SameSite is none."
        )

    bybit_status = {name: _configured(name) for name in BYBIT_PRIVATE_ENV_VARS}
    if any(bybit_status.values()) and not all(bybit_status.values()):
        missing = [name for name, configured in bybit_status.items() if not configured]
        raise RuntimeError(
            "Incomplete Bybit Demo credential configuration. Missing: " + ", ".join(missing)
        )

    supabase_status = {name: _configured(name) for name in SUPABASE_PRIVATE_ENV_VARS}
    if any(supabase_status.values()) and not all(supabase_status.values()):
        missing = [name for name, configured in supabase_status.items() if not configured]
        raise RuntimeError(
            "Incomplete Supabase backend configuration. Missing: " + ", ".join(missing)
        )

    messages = [
        "Environment validation passed: Bybit Demo endpoint is locked.",
        "Private single-token authentication is configured.",
        f"Authenticated sessions expire after {session_ttl_minutes} minutes.",
    ]
    if all(bybit_status.values()):
        messages.append("Backend-only Bybit Demo credentials are configured.")
    else:
        messages.append(
            "Backend-only Bybit Demo credentials are not configured; private exchange operations remain unavailable."
        )

    if all(supabase_status.values()):
        messages.append("Backend-only Supabase runtime persistence is configured.")
    else:
        messages.append("Supabase runtime persistence is not configured; existing local fallback remains active.")
    return messages


class AppConfig(BaseModel):
    app_name: str = "TradeHawk Backend"
    version: str = "0.3.0"
    phase: str = "foundation"
    execution_enabled: bool = False
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    default_system_mode: RuntimeMode = RuntimeMode.DEMO
    default_strategy_mode: TradingMode = TradingMode.SCALPING
    runtime_state_path: Path = Path("outputs/runtime-state.json")
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_runtime_table: str = "runtime_state"
    supabase_runtime_row_key: str = "primary"
    supabase_timeout_seconds: float = 8.0
    access_token: SecretStr = SecretStr("")
    session_ttl_minutes: int = 480
    session_cookie_name: str = "tradehawk_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"

    @property
    def cors_origins(self) -> list[str]:
        return _parse_frontend_origins(self.frontend_url)


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    app_env = getenv("APP_ENV", "development")
    return AppConfig(
        app_name=getenv("APP_NAME", "TradeHawk Backend"),
        app_env=app_env,
        app_host=getenv("APP_HOST", "127.0.0.1"),
        app_port=int(getenv("APP_PORT", "8000")),
        frontend_url=getenv("FRONTEND_URL", "http://localhost:3000"),
        default_system_mode=RuntimeMode(getenv("DEFAULT_SYSTEM_MODE", "demo")),
        default_strategy_mode=TradingMode(
            getenv("DEFAULT_STRATEGY_MODE", "scalping")
        ),
        runtime_state_path=Path(
            getenv("RUNTIME_STATE_PATH", str(Path("outputs/runtime-state.json")))
        ),
        supabase_url=getenv("SUPABASE_URL"),
        supabase_service_role_key=getenv("SUPABASE_SERVICE_ROLE_KEY"),
        supabase_runtime_table=getenv("SUPABASE_RUNTIME_TABLE", "runtime_state"),
        supabase_runtime_row_key=getenv("SUPABASE_RUNTIME_ROW_KEY", "primary"),
        supabase_timeout_seconds=float(getenv("SUPABASE_TIMEOUT_SECONDS", "8")),
        access_token=SecretStr((getenv("TRADEHAWK_ACCESS_TOKEN") or "").strip()),
        session_ttl_minutes=_parse_positive_int(
            "TRADEHAWK_SESSION_TTL_MINUTES", default=480, maximum=1440
        ),
        session_cookie_name=getenv("TRADEHAWK_SESSION_COOKIE_NAME", "tradehawk_session"),
        session_cookie_secure=_parse_bool(
            "TRADEHAWK_SESSION_COOKIE_SECURE",
            default=app_env.strip().lower() not in {"development", "test"},
        ),
        session_cookie_samesite=(
            getenv("TRADEHAWK_SESSION_COOKIE_SAMESITE") or "lax"
        ).strip().lower(),
    )
