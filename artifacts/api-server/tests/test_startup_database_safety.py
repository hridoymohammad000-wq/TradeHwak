import os
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main


class StartupDatabaseSafetyTests(unittest.TestCase):
    def test_startup_aborts_when_database_initialization_fails(self):
        stack = ExitStack()
        stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "DATABASE_URL": "postgres://example",
                    "TRADEHAWK_ACCESS_TOKEN": "test-secret",
                },
            )
        )
        stack.enter_context(
            patch.object(main.persistence_repository, "database_url", "postgres://example")
        )
        stack.enter_context(
            patch.object(main.persistence_repository, "initialize", return_value=False)
        )
        stack.enter_context(
            patch.object(
                main.persistence_repository,
                "last_error",
                "Database initialization failed: connection refused",
            )
        )
        stack.enter_context(patch.object(main, "_auto_trade_loop"))
        stack.enter_context(patch.object(main, "_trade_management_loop"))
        stack.enter_context(patch.object(main, "_exchange_reconciliation_loop"))
        self.addCleanup(stack.close)

        with self.assertRaises(RuntimeError) as context:
            stack.enter_context(TestClient(main.app))

        self.assertIn("Database initialization failed", str(context.exception))

    def test_startup_aborts_when_settings_restore_fails_after_readiness_check(self):
        stack = ExitStack()
        stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "DATABASE_URL": "postgres://example",
                    "TRADEHAWK_ACCESS_TOKEN": "test-secret",
                },
            )
        )
        stack.enter_context(
            patch.object(main.persistence_repository, "database_url", "postgres://example")
        )
        stack.enter_context(
            patch.object(main.persistence_repository, "initialize", return_value=True)
        )
        stack.enter_context(
            patch.object(main.persistence_repository, "verify_execution_ready", return_value=(True, None))
        )
        stack.enter_context(
            patch.object(
                main.settings_service,
                "reload_from_persistence",
                side_effect=RuntimeError("Database read failed: settings restore failed"),
            )
        )
        stack.enter_context(patch.object(main, "_auto_trade_loop"))
        stack.enter_context(patch.object(main, "_trade_management_loop"))
        stack.enter_context(patch.object(main, "_exchange_reconciliation_loop"))
        self.addCleanup(stack.close)

        with self.assertRaises(RuntimeError) as context:
            stack.enter_context(TestClient(main.app))

        self.assertIn("settings restore failed", str(context.exception))


if __name__ == "__main__":
    unittest.main()
