import unittest
from unittest.mock import patch

from app.services.bybit_service import BybitService


class StubClosedKlinesService(BybitService):
    def __init__(self) -> None:
        super().__init__()
        self.last_query = None

    def _validate_symbol(self, symbol: str) -> dict:
        return {"symbol": str(symbol).upper(), "instrument": {}}

    def _public_get(self, endpoint: str, query: str) -> dict:
        self.last_query = query
        rows = []
        base_open_ms = 1_700_000_000_000
        for index in range(22):
            open_ms = base_open_ms + (index * 60_000)
            rows.append(
                [
                    str(open_ms),
                    "100",
                    "101",
                    "99",
                    "100.5",
                    "123",
                ]
            )
        return {"result": {"list": list(reversed(rows))}}


class BybitClosedKlinesTests(unittest.TestCase):
    def test_overfetch_preserves_requested_closed_count_when_latest_row_is_open(self):
        service = StubClosedKlinesService()
        latest_open_ms = 1_700_000_000_000 + (21 * 60_000)
        now_seconds = (latest_open_ms + 30_000) / 1000

        with patch("app.services.bybit_service.time.time", return_value=now_seconds):
            payload = service._get_closed_klines("BTCUSDT", "1", limit=20)

        self.assertIn("limit=22", service.last_query)
        self.assertEqual(len(payload["result"]["list"]), 20)
        returned_open_times = [int(row[0]) for row in payload["result"]["list"]]
        self.assertNotIn(latest_open_ms, returned_open_times)


if __name__ == "__main__":
    unittest.main()
