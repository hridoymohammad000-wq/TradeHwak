import asyncio
import os
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main
from app.api.routes import auth


class ApiAuthenticationRouteTests(unittest.TestCase):
    @staticmethod
    async def _idle_background_loop():
        await asyncio.Event().wait()

    def setUp(self):
        auth._FAILED_LOGINS.clear()
        auth._LOCKED_UNTIL.clear()

    def _client(self):
        stack = ExitStack()
        stack.enter_context(patch.object(main.persistence_repository, "initialize"))
        stack.enter_context(
            patch.object(main.persistence_repository, "verify_execution_ready", return_value=(True, None))
        )
        stack.enter_context(patch.object(main.settings_service, "reload_from_persistence"))
        stack.enter_context(patch.object(main.trade_service, "reload_from_persistence"))
        stack.enter_context(patch.object(main.profit_tracking_service, "reload_from_persistence"))
        stack.enter_context(patch.object(main, "_auto_trade_loop", self._idle_background_loop))
        stack.enter_context(patch.object(main, "_trade_management_loop", self._idle_background_loop))
        stack.enter_context(patch.object(main, "_exchange_reconciliation_loop", self._idle_background_loop))
        stack.enter_context(patch.dict(os.environ, {"TRADEHAWK_ACCESS_TOKEN": "test-secret"}))
        client = stack.enter_context(TestClient(main.app))
        self.addCleanup(stack.close)
        return client

    def test_protected_api_route_requires_authenticated_session(self):
        client = self._client()

        response = client.get("/api/settings")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "Authentication required.")

    def test_protected_api_route_accepts_valid_session_cookie(self):
        client = self._client()
        expiry = 4_102_444_800
        session_cookie = auth._sign(expiry, "test-secret")
        client.cookies.set(auth.COOKIE_NAME, session_cookie)

        response = client.get("/api/settings")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Settings fetched successfully.")

    def test_auth_session_endpoint_remains_public_but_validates_cookie(self):
        client = self._client()

        response = client.get("/api/auth/session")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "Authentication required.")

    def test_login_requires_trusted_origin_for_mutation_requests(self):
        client = self._client()

        response = client.post("/auth/login", json={"access_token": "test-secret"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["message"],
            "Origin validation failed for this mutation request.",
        )

    def test_login_accepts_same_origin_request(self):
        client = self._client()

        response = client.post(
            "/auth/login",
            json={"access_token": "test-secret"},
            headers={"Origin": "http://testserver"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "Login successful.")

    def test_login_rate_limits_repeated_failures(self):
        client = self._client()
        for _ in range(4):
            response = client.post(
                "/auth/login",
                json={"access_token": "wrong-secret"},
                headers={"Origin": "http://testserver"},
            )
            self.assertEqual(response.status_code, 401)

        blocked = client.post(
            "/auth/login",
            json={"access_token": "wrong-secret"},
            headers={"Origin": "http://testserver"},
        )

        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(
            blocked.json()["message"],
            "Too many failed login attempts. Try again later.",
        )


if __name__ == "__main__":
    unittest.main()
