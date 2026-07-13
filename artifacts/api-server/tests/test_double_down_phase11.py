import asyncio
import os
import unittest
from contextlib import ExitStack
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from app import main
from app.api.routes import auth, challenge
from app.double_down.service import ChallengeService
from app.services.system_service import SystemService


class FailingPersistence:
    def __init__(self) -> None:
        self.saved = {}
        self.fail_next_save = False

    def save_snapshot(self, challenge_id: UUID, snapshot: dict) -> None:
        if self.fail_next_save:
            self.fail_next_save = False
            raise RuntimeError("challenge persistence unavailable")
        self.saved[str(challenge_id)] = snapshot

    def load_snapshot(self, challenge_id: UUID) -> dict | None:
        return self.saved.get(str(challenge_id))

    def list_snapshots(self) -> list[dict]:
        return list(self.saved.values())


class DoubleDownPhase11Tests(unittest.TestCase):
    @staticmethod
    async def _idle_background_loop():
        await asyncio.Event().wait()

    def _client(self):
        stack = ExitStack()
        stack.enter_context(patch.object(main.persistence_repository, "initialize"))
        stack.enter_context(patch.object(main.settings_service, "reload_from_persistence"))
        stack.enter_context(patch.object(main.trade_service, "reload_from_persistence"))
        stack.enter_context(patch.object(main.profit_tracking_service, "reload_from_persistence"))
        stack.enter_context(patch.object(main, "_auto_trade_loop", self._idle_background_loop))
        stack.enter_context(patch.object(main, "_trade_management_loop", self._idle_background_loop))
        stack.enter_context(patch.object(main, "_exchange_reconciliation_loop", self._idle_background_loop))
        stack.enter_context(patch.dict(os.environ, {"TRADEHAWK_ACCESS_TOKEN": "test-secret"}))
        client = stack.enter_context(TestClient(main.app))
        expiry = 4_102_444_800
        session_cookie = auth._sign(expiry, "test-secret")
        client.cookies.set(auth.COOKIE_NAME, session_cookie)
        self.addCleanup(stack.close)
        return client

    def test_create_does_not_cache_unsaved_challenge(self):
        persistence = FailingPersistence()
        persistence.fail_next_save = True
        service = ChallengeService(persistence)

        with self.assertRaisesRegex(RuntimeError, "challenge persistence unavailable"):
            service.create(
                starting_balance=Decimal("100"),
                failure_floor=Decimal("20"),
            )

        self.assertEqual(service.list(), [])

    def test_state_change_rolls_back_when_persistence_fails(self):
        persistence = FailingPersistence()
        service = ChallengeService(persistence)
        created = service.create(
            starting_balance=Decimal("100"),
            failure_floor=Decimal("20"),
        )
        challenge_id = UUID(created["config"]["challenge_id"])
        persistence.fail_next_save = True

        with self.assertRaisesRegex(RuntimeError, "challenge persistence unavailable"):
            service.start(challenge_id)

        restored = service.get(challenge_id)
        self.assertEqual(restored["state"]["status"], "ready")

    def test_route_returns_message_data_envelope(self):
        client = self._client()
        snapshot = {
            "config": {"challenge_id": "00000000-0000-0000-0000-000000000001"},
            "state": {"status": "ready"},
            "ledger": [],
        }
        with patch.object(challenge, "challenge_service") as service:
            service.list.return_value = [snapshot]

            response = client.get("/api/challenge")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Challenges fetched successfully.")
        self.assertEqual(response.json()["data"], [snapshot])

    def test_route_converts_persistence_failure_to_backend_message(self):
        client = self._client()
        with patch.object(challenge, "challenge_service") as service:
            service.create.side_effect = RuntimeError("challenge persistence unavailable")

            response = client.post(
                "/api/challenge",
                json={"starting_balance": 100, "failure_floor": 20},
                headers={"Origin": "http://testserver"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["message"], "challenge persistence unavailable")

    def test_health_readiness_includes_double_down_persistence(self):
        repository = type(
            "RepositoryStub",
            (),
            {
                "verify_execution_ready": staticmethod(
                    lambda: (
                        False,
                        "Required database tables are missing: double_down_challenges",
                    )
                )
            },
        )()

        health = SystemService(repository=repository).get_health()

        self.assertEqual(health.data.status, "degraded")
        self.assertFalse(health.data.persistence_ready)
        self.assertIn("double_down_challenges", health.data.block_reason)


if __name__ == "__main__":
    unittest.main()
