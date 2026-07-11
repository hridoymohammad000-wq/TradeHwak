import unittest
from decimal import Decimal
from uuid import UUID

from app.double_down.service import ChallengeService


class MemoryChallengePersistence:
    def __init__(self):
        self.snapshots = {}

    def save_snapshot(self, challenge_id: UUID, snapshot: dict) -> None:
        self.snapshots[str(challenge_id)] = snapshot

    def load_snapshot(self, challenge_id: UUID):
        return self.snapshots.get(str(challenge_id))

    def list_snapshots(self):
        return list(self.snapshots.values())


class DoubleDownPhase9Tests(unittest.TestCase):
    def setUp(self):
        self.persistence = MemoryChallengePersistence()
        self.service = ChallengeService(self.persistence)

    def test_create_persists_ready_challenge(self):
        snapshot = self.service.create(
            starting_balance=Decimal("100"),
            failure_floor=Decimal("20"),
        )
        challenge_id = snapshot["config"]["challenge_id"]
        self.assertEqual(snapshot["state"]["status"], "ready")
        self.assertIn(challenge_id, self.persistence.snapshots)
        self.assertEqual(snapshot["ledger"][0]["balance_after"], "100")

    def test_start_pause_resume_and_terminate_are_persisted(self):
        created = self.service.create(
            starting_balance=Decimal("100"),
            failure_floor=Decimal("20"),
        )
        challenge_id = UUID(created["config"]["challenge_id"])
        self.assertEqual(self.service.start(challenge_id)["state"]["status"], "running")
        self.assertEqual(self.service.pause(challenge_id)["state"]["status"], "paused")
        self.assertEqual(self.service.resume(challenge_id)["state"]["status"], "running")
        self.assertEqual(self.service.terminate(challenge_id)["state"]["status"], "terminated")
        self.assertEqual(
            self.persistence.snapshots[str(challenge_id)]["state"]["status"],
            "terminated",
        )

    def test_restart_rehydrates_snapshot(self):
        created = self.service.create(
            starting_balance=Decimal("100"),
            failure_floor=Decimal("20"),
        )
        challenge_id = UUID(created["config"]["challenge_id"])
        self.service.start(challenge_id)

        restarted = ChallengeService(self.persistence)
        restored = restarted.get(challenge_id)

        self.assertEqual(restored["state"]["status"], "running")
        self.assertEqual(restored["config"]["challenge_id"], str(challenge_id))
        self.assertEqual(len(restored["ledger"]), 1)

    def test_list_deduplicates_memory_and_database_snapshots(self):
        created = self.service.create(
            starting_balance=Decimal("100"),
            failure_floor=Decimal("20"),
        )
        items = self.service.list()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["config"]["challenge_id"], created["config"]["challenge_id"])

    def test_unknown_challenge_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.service.get(UUID("00000000-0000-0000-0000-000000000001"))


if __name__ == "__main__":
    unittest.main()
