import unittest

from app.db.repository import PersistenceRepository


class FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self, acquired=True, released=True):
        self.acquired = acquired
        self.released = released
        self.closed = False
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql, params))
        if "pg_try_advisory_lock" in sql:
            return FakeCursor({"acquired": self.acquired})
        if "pg_advisory_unlock" in sql:
            return FakeCursor({"released": self.released})
        raise AssertionError(f"Unexpected SQL: {sql}")

    def close(self):
        self.closed = True


class DistributedLockRepairTests(unittest.TestCase):
    def test_acquired_lock_connection_stays_open_until_unlock(self):
        repository = PersistenceRepository(database_url="postgres://example")
        repository.enabled = True
        repository._pool = None
        connection = FakeConnection(acquired=True, released=True)
        repository._connect = lambda: connection

        acquired = repository.try_advisory_lock("tradehawk:auto_trade_cycle")

        self.assertTrue(acquired)
        self.assertFalse(connection.closed)
        self.assertIn(
            "tradehawk:auto_trade_cycle",
            repository._advisory_lock_connections,
        )

        released = repository.advisory_unlock("tradehawk:auto_trade_cycle")

        self.assertTrue(released)
        self.assertTrue(connection.closed)
        self.assertNotIn(
            "tradehawk:auto_trade_cycle",
            repository._advisory_lock_connections,
        )

    def test_failed_lock_attempt_closes_connection_immediately(self):
        repository = PersistenceRepository(database_url="postgres://example")
        repository.enabled = True
        repository._pool = None
        connection = FakeConnection(acquired=False, released=False)
        repository._connect = lambda: connection

        acquired = repository.try_advisory_lock("tradehawk:auto_trade_cycle")

        self.assertFalse(acquired)
        self.assertTrue(connection.closed)
        self.assertEqual(repository._advisory_lock_connections, {})


if __name__ == "__main__":
    unittest.main()
