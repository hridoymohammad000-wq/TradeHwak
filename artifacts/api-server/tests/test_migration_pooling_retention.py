import unittest
from unittest.mock import patch

from app.db import repository as repository_module
from app.db.repository import PersistenceRepository


class FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or []

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConnection:
    def __init__(self):
        self.statements = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=()):
        statement = " ".join(str(sql).split())
        self.statements.append((statement, params))
        if "SELECT version FROM schema_migrations" in statement:
            return FakeCursor([])
        if "pg_try_advisory_lock" in statement:
            return FakeCursor([{"acquired": True}])
        if "pg_advisory_unlock" in statement:
            return FakeCursor([{"released": True}])
        return FakeCursor([])

    def close(self):
        self.closed = True


class FakePsycopg:
    def __init__(self):
        self.connection = FakeConnection()

    def connect(self, *args, **kwargs):
        return self.connection


class FakePool:
    def __init__(self, *args, **kwargs):
        self.connection = FakeConnection()
        self.opened = False
        self.closed = False
        self.returned = 0

    def open(self, wait=False):
        self.opened = True

    def getconn(self):
        return self.connection

    def putconn(self, connection):
        self.returned += 1

    def close(self):
        self.closed = True


class MigrationPoolingRetentionTests(unittest.TestCase):
    def test_initialize_applies_versioned_migrations_and_cleans_old_logs(self):
        fake_psycopg = FakePsycopg()
        with patch.object(repository_module, "psycopg", fake_psycopg), patch.object(
            repository_module, "dict_row", object()
        ), patch.object(repository_module, "ConnectionPool", None):
            repository = PersistenceRepository(
                "postgres://example",
                log_retention_days=9,
            )

            self.assertTrue(repository.initialize())

        statements = [statement for statement, _ in fake_psycopg.connection.statements]
        self.assertTrue(
            any("CREATE TABLE IF NOT EXISTS schema_migrations" in statement for statement in statements)
        )
        self.assertTrue(
            any("INSERT INTO schema_migrations" in statement for statement in statements)
        )
        cleanup_statements = [
            item
            for item in fake_psycopg.connection.statements
            if "DELETE FROM" in item[0] and "created_at < now()" in item[0]
        ]
        self.assertEqual(len(cleanup_statements), 3)
        self.assertTrue(all(params == (9,) for _, params in cleanup_statements))

    def test_pool_returns_connections_and_closes_cleanly(self):
        with patch.object(repository_module, "psycopg", object()), patch.object(
            repository_module, "dict_row", object()
        ), patch.object(repository_module, "ConnectionPool", FakePool):
            repository = PersistenceRepository(
                "postgres://example",
                pool_min_size=1,
                pool_max_size=2,
            )
            repository.execute_required("SELECT 1")
            pool = repository._pool
            repository.close()

        self.assertTrue(pool.opened)
        self.assertEqual(pool.returned, 1)
        self.assertTrue(pool.closed)


if __name__ == "__main__":
    unittest.main()
