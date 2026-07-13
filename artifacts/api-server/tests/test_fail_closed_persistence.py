import unittest
from uuid import uuid4

from app.db.repository import PersistenceRepository
from app.double_down.persistence import ChallengePersistence
from app.services.settings_service import SettingsService
from app.services.trade_service import TradeService


class FailClosedPersistenceTests(unittest.TestCase):
    def test_save_settings_raises_when_persistence_is_disabled(self):
        repository = PersistenceRepository(database_url="")

        with self.assertRaises(RuntimeError) as context:
            repository.save_settings({"system_mode": "demo"})

        self.assertIn("disabled", str(context.exception).lower())

    def test_executed_signal_save_raises_when_persistence_is_disabled(self):
        repository = PersistenceRepository(database_url="")

        with self.assertRaises(RuntimeError):
            repository.save_executed_signal_id("sig-1", None)

    def test_challenge_snapshot_save_raises_when_persistence_is_disabled(self):
        repository = PersistenceRepository(database_url="")
        persistence = ChallengePersistence(repository)

        with self.assertRaises(RuntimeError):
            persistence.save_snapshot(uuid4(), {"state": {"status": "ready"}})

    def test_settings_load_raises_when_persistence_is_disabled(self):
        repository = PersistenceRepository(database_url="")

        with self.assertRaises(RuntimeError):
            repository.load_settings()

    def test_trade_state_load_raises_when_persistence_is_disabled(self):
        repository = PersistenceRepository(database_url="")

        with self.assertRaises(RuntimeError):
            repository.load_trade_state()

    def test_reload_from_persistence_aborts_on_database_read_failure(self):
        class BrokenRepository:
            def load_settings(self):
                raise RuntimeError("Database read failed: connection dropped")

        with self.assertRaises(RuntimeError):
            SettingsService(repository=BrokenRepository()).reload_from_persistence()

    def test_trade_restore_aborts_on_invalid_persisted_trade_payload(self):
        class InvalidTradeRepository:
            def load_trade_state(self):
                return ([{"symbol": "BTCUSDT"}], [])

            def load_executed_signal_ids(self, trade_day):
                return set()

        service = TradeService(
            settings_service=SettingsService(repository=None),
            repository=InvalidTradeRepository(),
        )

        with self.assertRaises(RuntimeError):
            service.reload_from_persistence()


if __name__ == "__main__":
    unittest.main()
