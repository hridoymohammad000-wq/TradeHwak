from __future__ import annotations

import json
import logging
import zlib
from contextlib import contextmanager, suppress
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


class PersistenceRepository:
    """Small synchronous Postgres repository."""

    REQUIRED_EXECUTION_TABLES = (
        "bot_settings",
        "trade_history",
        "executed_signal_ids",
        "profit_tracking_state",
        "workflow_state",
        "execution_logs",
        "double_down_challenges",
    )

    def __init__(self, database_url: str | None) -> None:
        self.database_url = (database_url or "").strip()
        self.enabled = bool(self.database_url and psycopg is not None)
        self.last_error: str | None = None
        self._advisory_lock_connections: dict[str, Any] = {}
        if self.database_url and psycopg is None:
            self.last_error = "DATABASE_URL is set but psycopg is not installed."
            logger.warning(self.last_error)

    def initialize(self) -> bool:
        if not self.enabled:
            return False
        sql_path = Path(__file__).resolve().parents[2] / "migrations" / "001_init.sql"
        try:
            with self._connect() as connection:
                connection.execute(sql_path.read_text(encoding="utf-8"))
            self.last_error = None
            return True
        except Exception as exc:
            self._handle_error("Database initialization failed", exc)
            return False

    def verify_execution_ready(self) -> tuple[bool, str | None]:
        if not self.database_url:
            return False, "DATABASE_URL is not configured."
        if psycopg is None:
            return False, "psycopg is not installed; PostgreSQL persistence is unavailable."
        if not self.enabled:
            return False, self.last_error or "Database persistence is disabled."

        try:
            with self._connect() as connection:
                missing_tables = []
                for table in self.REQUIRED_EXECUTION_TABLES:
                    row = connection.execute(
                        "SELECT to_regclass(%s) AS table_name",
                        (f"public.{table}",),
                    ).fetchone()
                    if not row or row.get("table_name") is None:
                        missing_tables.append(table)
                if missing_tables:
                    return (
                        False,
                        "Required database tables are missing: "
                        + ", ".join(missing_tables),
                    )

                connection.execute("SELECT settings FROM bot_settings WHERE id = 1").fetchone()
                connection.execute("SELECT payload, status FROM trade_history LIMIT 1").fetchall()
                connection.execute("SELECT signal_id FROM executed_signal_ids LIMIT 1").fetchall()
                connection.execute("SELECT state FROM profit_tracking_state WHERE id = 1").fetchone()
                connection.execute("SELECT state FROM workflow_state WHERE id = 1").fetchone()
                connection.execute("SELECT snapshot FROM double_down_challenges LIMIT 1").fetchall()
                self.last_error = None
                return True, None
        except Exception as exc:
            self._handle_error("Database readiness check failed", exc)
            return False, self.last_error

    def load_settings(self) -> dict[str, Any] | None:
        row = self._fetchone("SELECT settings FROM bot_settings WHERE id = 1")
        return self._json_value(row.get("settings")) if row else None

    def save_settings(self, settings: dict[str, Any]) -> None:
        self._execute_required("""
            INSERT INTO bot_settings (id, settings, updated_at)
            VALUES (1, %s::jsonb, now())
            ON CONFLICT (id) DO UPDATE SET settings = EXCLUDED.settings, updated_at = now()
        """, (self._json(settings),))

    def load_trade_state(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows = self._fetchall("SELECT payload, status FROM trade_history ORDER BY created_at ASC")
        active, closed = [], []
        for row in rows:
            payload = self._json_value(row.get("payload")) or {}
            (closed if row.get("status") == "closed" else active).append(payload)
        return active, closed

    def upsert_trade(self, trade_key: str, status: str, payload: dict[str, Any]) -> None:
        self._execute_required("""
            INSERT INTO trade_history (trade_key, status, payload, updated_at)
            VALUES (%s, %s, %s::jsonb, now())
            ON CONFLICT (trade_key) DO UPDATE
            SET status = EXCLUDED.status, payload = EXCLUDED.payload, updated_at = now()
        """, (trade_key, status, self._json(payload)))

    def save_journal_entry(self, trade_key: str, payload: dict[str, Any]) -> None:
        self._execute_required("""
            INSERT INTO journal (trade_key, payload, created_at)
            VALUES (%s, %s::jsonb, now())
            ON CONFLICT (trade_key) DO UPDATE SET payload = EXCLUDED.payload
        """, (trade_key, self._json(payload)))

    def load_executed_signal_ids(self, trade_day: date) -> set[str]:
        rows = self._fetchall("SELECT signal_id FROM executed_signal_ids WHERE trade_day = %s", (trade_day,))
        return {str(row["signal_id"]) for row in rows}

    def save_executed_signal_id(self, signal_id: str, trade_day: date) -> None:
        self._execute_required("""
            INSERT INTO executed_signal_ids (signal_id, trade_day)
            VALUES (%s, %s)
            ON CONFLICT (signal_id, trade_day) DO NOTHING
        """, (signal_id, trade_day))

    def load_profit_tracking_state(self) -> dict[str, Any] | None:
        row = self._fetchone("SELECT state FROM profit_tracking_state WHERE id = 1")
        return self._json_value(row.get("state")) if row else None

    def save_profit_tracking_state(self, state: dict[str, Any]) -> None:
        self._execute_required("""
            INSERT INTO profit_tracking_state (id, state, updated_at)
            VALUES (1, %s::jsonb, now())
            ON CONFLICT (id) DO UPDATE SET state = EXCLUDED.state, updated_at = now()
        """, (self._json(state),))

    def load_trade_management_state(self) -> dict[str, Any] | None:
        row = self._fetchone("SELECT state FROM trade_management_state WHERE id = 1")
        return self._json_value(row.get("state")) if row else None

    def save_trade_management_state(self, state: dict[str, Any]) -> None:
        self._execute_required("""
            INSERT INTO trade_management_state (id, state, updated_at)
            VALUES (1, %s::jsonb, now())
            ON CONFLICT (id) DO UPDATE SET state = EXCLUDED.state, updated_at = now()
        """, (self._json(state),))

    def load_workflow_state(self) -> dict[str, Any] | None:
        row = self._fetchone("SELECT state FROM workflow_state WHERE id = 1")
        return self._json_value(row.get("state")) if row else None

    def save_workflow_state(self, state: dict[str, Any]) -> None:
        self._execute_required("""
            INSERT INTO workflow_state (id, state, updated_at)
            VALUES (1, %s::jsonb, now())
            ON CONFLICT (id) DO UPDATE SET state = EXCLUDED.state, updated_at = now()
        """, (self._json(state),))

    def execute_required(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self._execute_required(sql, params)

    def append_log(self, table: str, event_type: str, payload: dict[str, Any]) -> None:
        allowed = {"scan_logs", "signal_logs", "execution_logs"}
        if table not in allowed:
            raise ValueError(f"Unsupported log table: {table}")
        self._execute(f"INSERT INTO {table} (event_type, payload) VALUES (%s, %s::jsonb)", (event_type, self._json(payload)))

    @contextmanager
    def advisory_lock_session(self, name: str):
        if not self.enabled:
            yield True
            return
        if name in self._advisory_lock_connections:
            yield True
            return

        key = self._advisory_lock_key(name)
        connection = None
        acquired = False
        try:
            connection = self._connect()
            row = connection.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired",
                (key,),
            ).fetchone()
            acquired = bool(row and row.get("acquired"))
            if not acquired:
                with suppress(Exception):
                    connection.close()
                yield False
                return
            self._advisory_lock_connections[name] = connection
            self.last_error = None
            yield True
        except Exception as exc:
            if connection is not None:
                with suppress(Exception):
                    connection.close()
            self._handle_error("Advisory lock acquisition failed", exc)
            yield False
        finally:
            held = self._advisory_lock_connections.pop(name, None)
            if acquired and held is not None:
                try:
                    held.execute(
                        "SELECT pg_advisory_unlock(%s) AS released",
                        (key,),
                    ).fetchone()
                    self.last_error = None
                except Exception as exc:
                    self._handle_error("Advisory lock release failed", exc)
                finally:
                    with suppress(Exception):
                        held.close()

    def try_advisory_lock(self, name: str) -> bool:
        if not self.enabled:
            return True
        if name in self._advisory_lock_connections:
            return True
        key = self._advisory_lock_key(name)
        connection = None
        try:
            connection = self._connect()
            row = connection.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired",
                (key,),
            ).fetchone()
            acquired = bool(row and row.get("acquired"))
            if acquired:
                self._advisory_lock_connections[name] = connection
                self.last_error = None
                return True
            connection.close()
            return False
        except Exception as exc:
            if connection is not None:
                with suppress(Exception):
                    connection.close()
            self._handle_error("Advisory lock acquisition failed", exc)
            return False

    def advisory_unlock(self, name: str) -> bool:
        if not self.enabled:
            return True
        key = self._advisory_lock_key(name)
        connection = self._advisory_lock_connections.pop(name, None)
        if connection is None:
            return False
        try:
            row = connection.execute(
                "SELECT pg_advisory_unlock(%s) AS released",
                (key,),
            ).fetchone()
            self.last_error = None
            return bool(row and row.get("released"))
        except Exception as exc:
            self._handle_error("Advisory lock release failed", exc)
            return False
        finally:
            with suppress(Exception):
                connection.close()

    def _connect(self):
        if not self.enabled or psycopg is None:
            raise RuntimeError("Database persistence is disabled.")
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        if not self.enabled:
            return
        try:
            with self._connect() as connection:
                connection.execute(sql, params)
            self.last_error = None
        except Exception as exc:
            self._handle_error("Database write failed", exc)

    def _execute_required(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        if not self.enabled:
            reason = self.last_error or "Database persistence is disabled."
            raise RuntimeError(reason)
        try:
            with self._connect() as connection:
                connection.execute(sql, params)
            self.last_error = None
        except Exception as exc:
            self._handle_error("Database write failed", exc)
            raise RuntimeError(self.last_error) from exc

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            with self._connect() as connection:
                row = connection.execute(sql, params).fetchone()
            self.last_error = None
            return row
        except Exception as exc:
            self._handle_error("Database read failed", exc)
            return None

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            with self._connect() as connection:
                rows = connection.execute(sql, params).fetchall()
            self.last_error = None
            return list(rows)
        except Exception as exc:
            self._handle_error("Database read failed", exc)
            return []

    def _handle_error(self, prefix: str, exc: Exception) -> None:
        self.last_error = f"{prefix}: {exc}"
        logger.warning(self.last_error)

    @staticmethod
    def _json(payload: dict[str, Any]) -> str:
        return json.dumps(payload, default=PersistenceRepository._json_default)

    @staticmethod
    def _json_value(value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return value

    @staticmethod
    def _json_default(value: Any) -> str:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    @staticmethod
    def _advisory_lock_key(name: str) -> int:
        return zlib.crc32(name.encode("utf-8")) & 0x7FFFFFFF
