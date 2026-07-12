import unittest
from uuid import uuid4

from app.db.repository import PersistenceRepository
from app.double_down.persistence import ChallengePersistence


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


if __name__ == "__main__":
    unittest.main()
