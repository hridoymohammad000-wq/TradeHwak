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

try:
    from psycopg_pool import ConnectionPool
except ImportError:
    ConnectionPool = None


class PersistenceRepository:
    """Small synchronous Postgres repository."""

    REQUIRED_EXECUTION_TABLES = (
        "schema_migrations",
        "bot_settings",
        "trade_history",
        "executed_signal_ids",
        "profit_tracking_state",
        "workflow_state",
        "execution_logs",
        "double_down_challenges",
    )

    LOG_TABLES = ("scan_logs", "signal_logs", "execution_logs")

    def __init__(
        self,
        database_url: str | None,
        *,
        pool_min_size: int = 1,
        pool_max_size: int = 5,
        log_retention_days: int = 14,
    ) -> None:
        self.database_url = (database_url or "").strip()
        self.enabled = bool(self.database_url and psycopg is not None)
        self.last_error: str | None = None
        self._advisory_lock_connections: dict[str, Any] = {}
        self._pool: Any | None = None
        self._pool_min_size = max(0, int(pool_min_size))
        self._pool_max_size = max(1, int(pool_max_size))
        if self._pool_min_size > self._pool_max_size:
            self._pool_min_size = self._pool_max_size
        self.log_retention_days = max(1, int(log_retention_days))
        if self.database_url and psycopg is None:
            self.last_error = "DATABASE_URL is set but psycopg is not installed."
            logger.warning(self.last_error)
        if self.enabled and ConnectionPool is not None:
            self._pool = ConnectionPool(
                self.database_url,
                min_size=self._pool_min_size,
                max_size=self._pool_max_size,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            self._pool.open(wait=False)
        elif self.enabled and ConnectionPool is None:
            self.last_error = "psycopg_pool is not installed; using direct database connections."
            logger.warning(self.last_error)

    def initialize(self) -> bool:
        if not self.enabled:
            return False
        try:
            self._run_migrations()
            self.cleanup_old_logs()
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
            with self._connection() as connection:
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
        row = self._fetchone_required("SELECT settings FROM bot_settings WHERE id = 1")
        return self._json_value(row.get("settings")) if row else None

    def save_settings(self, settings: dict[str, Any]) -> None:
        self._execute_required("""
            INSERT INTO bot_settings (id, settings, updated_at)
            VALUES (1, %s::jsonb, now())
            ON CONFLICT (id) DO UPDATE SET settings = EXCLUDED.settings, updated_at = now()
        """, (self._json(settings),))

    def load_trade_state(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows = self._fetchall_required(
            "SELECT payload, status FROM trade_history ORDER BY created_at ASC"
        )
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

    def delete_trade(self, trade_key: str) -> None:
        self._execute_required(
            "DELETE FROM trade_history WHERE trade_key = %s",
            (trade_key,),
        )

    def delete_journal_entry(self, trade_key: str) -> None:
        self._execute_required(
            "DELETE FROM journal WHERE trade_key = %s",
            (trade_key,),
        )

    def load_executed_signal_ids(self, trade_day: date) -> set[str]:
        rows = self._fetchall_required(
            "SELECT signal_id FROM executed_signal_ids WHERE trade_day = %s",
            (trade_day,),
        )
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
        if table not in self.LOG_TABLES:
            raise ValueError(f"Unsupported log table: {table}")
        self._execute(f"INSERT INTO {table} (event_type, payload) VALUES (%s, %s::jsonb)", (event_type, self._json(payload)))

    def cleanup_old_logs(self) -> None:
        if not self.enabled:
            return
        for table in self.LOG_TABLES:
            self._execute_required(
                f"DELETE FROM {table} WHERE created_at < now() - (%s * interval '1 day')",
                (self.log_retention_days,),
            )

    def close(self) -> None:
        for name in list(self._advisory_lock_connections):
            self.advisory_unlock(name)
        if self._pool is not None:
            with suppress(Exception):
                self._pool.close()

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
            connection = self._acquire_connection()
            row = connection.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired",
                (key,),
            ).fetchone()
            acquired = bool(row and row.get("acquired"))
            if not acquired:
                with suppress(Exception):
                    self._release_connection(connection)
                yield False
                return
            self._advisory_lock_connections[name] = connection
            self.last_error = None
            yield True
        except Exception as exc:
            if connection is not None:
                self._release_connection(connection)
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
                    self._release_connection(held)

    def try_advisory_lock(self, name: str) -> bool:
        if not self.enabled:
            return True
        if name in self._advisory_lock_connections:
            return True
        key = self._advisory_lock_key(name)
        connection = None
        try:
            connection = self._acquire_connection()
            row = connection.execute(
                "SELECT pg_try_advisory_lock(%s) AS acquired",
                (key,),
            ).fetchone()
            acquired = bool(row and row.get("acquired"))
            if acquired:
                self._advisory_lock_connections[name] = connection
                self.last_error = None
                return True
            self._release_connection(connection)
            return False
        except Exception as exc:
            if connection is not None:
                self._release_connection(connection)
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
                self._release_connection(connection)

    def _acquire_connection(self):
        if not self.enabled or psycopg is None:
            raise RuntimeError("Database persistence is disabled.")
        if self._pool is not None:
            return self._pool.getconn()
        return self._connect()

    def _connect(self):
        if not self.enabled or psycopg is None:
            raise RuntimeError("Database persistence is disabled.")
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _release_connection(self, connection) -> None:
        with suppress(Exception):
            if self._pool is not None:
                self._pool.putconn(connection)
            else:
                connection.close()

    @contextmanager
    def _connection(self):
        connection = self._acquire_connection()
        try:
            with connection:
                yield connection
        finally:
            self._release_connection(connection)

    def _run_migrations(self) -> None:
        migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
        migration_files = sorted(migrations_dir.glob("*.sql"))
        if not migration_files:
            raise RuntimeError("No database migrations were found.")

        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version text PRIMARY KEY,
                    filename text NOT NULL,
                    checksum integer NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
            """)
            applied_rows = connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
            applied = {str(row["version"]) for row in applied_rows}

            for path in migration_files:
                version = path.stem.split("_", 1)[0]
                if version in applied:
                    continue
                sql = path.read_text(encoding="utf-8")
                connection.execute(sql)
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version, filename, checksum)
                    VALUES (%s, %s, %s)
                    """,
                    (version, path.name, zlib.crc32(sql.encode("utf-8")) & 0x7FFFFFFF),
                )

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        if not self.enabled:
            return
        try:
            with self._connection() as connection:
                connection.execute(sql, params)
            self.last_error = None
        except Exception as exc:
            self._handle_error("Database write failed", exc)

    def _execute_required(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        if not self.enabled:
            reason = self.last_error or "Database persistence is disabled."
            raise RuntimeError(reason)
        try:
            with self._connection() as connection:
                connection.execute(sql, params)
            self.last_error = None
        except Exception as exc:
            self._handle_error("Database write failed", exc)
            raise RuntimeError(self.last_error) from exc

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            with self._connection() as connection:
                row = connection.execute(sql, params).fetchone()
            self.last_error = None
            return row
        except Exception as exc:
            self._handle_error("Database read failed", exc)
            return None

    def _fetchone_required(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        if not self.enabled:
            reason = self.last_error or "Database persistence is disabled."
            raise RuntimeError(reason)
        try:
            with self._connection() as connection:
                row = connection.execute(sql, params).fetchone()
            self.last_error = None
            return row
        except Exception as exc:
            self._handle_error("Database read failed", exc)
            raise RuntimeError(self.last_error) from exc

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            with self._connection() as connection:
                rows = connection.execute(sql, params).fetchall()
            self.last_error = None
            return list(rows)
        except Exception as exc:
            self._handle_error("Database read failed", exc)
            return []

    def _fetchall_required(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            reason = self.last_error or "Database persistence is disabled."
            raise RuntimeError(reason)
        try:
            with self._connection() as connection:
                rows = connection.execute(sql, params).fetchall()
            self.last_error = None
            return list(rows)
        except Exception as exc:
            self._handle_error("Database read failed", exc)
            raise RuntimeError(self.last_error) from exc

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
