import unittest
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from app.double_down.service import ChallengeService


@dataclass
class SnapshotData:
    mark_price: Decimal | None = None
    last_price: Decimal | None = None


class InMemoryPersistence:
    def __init__(self) -> None:
        self.saved: dict[str, dict] = {}

    def save_snapshot(self, challenge_id: UUID, snapshot: dict) -> None:
        self.saved[str(challenge_id)] = snapshot

    def load_snapshot(self, challenge_id: UUID) -> dict | None:
        return self.saved.get(str(challenge_id))

    def list_snapshots(self) -> list[dict]:
        return list(self.saved.values())


class FakeBybitService:
    def __init__(self) -> None:
        self.orders: dict[str, dict] = {}
        self.positions: dict[str, dict] = {}
        self.close_calls: list[dict] = []

    def _public_get(self, path: str, query: str) -> dict:
        return {
            "result": {
                "list": [
                    self._ticker_row("BTCUSDT", "0.01", "15000000", "2000", "100.00", "100.10", "100.05"),
                    self._ticker_row("ETHUSDT", "0.06", "12000000", "1800", "110.00", "110.08", "110.04"),
                    self._ticker_row("XRPUSDT", "-0.05", "11000000", "1600", "90.00", "90.05", "90.02"),
                ]
            }
        }

    def _get_closed_klines(self, symbol: str, interval: str, *, limit: int = 20) -> dict:
        if symbol == "XRPUSDT":
            rows = self._bearish_rows(symbol)
        else:
            rows = self._bullish_rows(symbol)
        return {"result": {"list": rows[-limit:]}}

    def get_validated_symbol(self, symbol: str) -> dict:
        return {
            "instrument": {
                "lotSizeFilter": {
                    "minOrderQty": "0.001",
                    "maxMktOrderQty": "1000",
                    "maxOrderQty": "1000",
                    "qtyStep": "0.001",
                    "minNotionalValue": "5",
                }
            }
        }

    def create_private_order(self, payload: dict) -> dict:
        order_id = f"order-{payload['orderLinkId']}"
        self.orders[payload["orderLinkId"]] = {
            "orderId": order_id,
            "symbol": payload["symbol"],
            "side": payload["side"],
            "qty": payload["qty"],
        }
        return {"result": {"orderId": order_id}, "retMsg": "OK"}

    def _private_post(self, path: str, payload: dict) -> dict:
        self.positions[payload["symbol"]] = {
            "positionIdx": 0,
            "stopLoss": payload["stopLoss"],
            "takeProfit": payload["takeProfit"],
        }
        return {"retMsg": "OK"}

    def get_order_history(self, *, symbol: str, order_link_id: str | None = None, limit: int = 10, order_id: str | None = None):
        if order_link_id and order_link_id in self.orders:
            return [self.orders[order_link_id]]
        return []

    def get_position(self, symbol: str) -> dict | None:
        return self.positions.get(symbol)

    def emergency_close_position(self, *, symbol: str, side: str, qty: str, order_link_id: str) -> dict:
        order_id = f"close-{order_link_id}"
        self.close_calls.append(
            {
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "order_link_id": order_link_id,
            }
        )
        self.positions.pop(symbol, None)
        return {"result": {"orderId": order_id}}

    def get_market_snapshot(self, symbol: str):
        prices = {
            "BTCUSDT": Decimal("101"),
            "ETHUSDT": Decimal("112"),
            "XRPUSDT": Decimal("88"),
        }
        return SimpleNamespace(data=SnapshotData(mark_price=prices[symbol], last_price=prices[symbol]))

    @staticmethod
    def _ticker_row(symbol: str, price_change_pct: str, turnover: str, volume: str, bid: str, ask: str, last: str) -> dict:
        return {
            "symbol": symbol,
            "price24hPcnt": price_change_pct,
            "turnover24h": turnover,
            "volume24h": volume,
            "bid1Price": bid,
            "ask1Price": ask,
            "lastPrice": last,
        }

    @staticmethod
    def _bullish_rows(symbol: str) -> list[list[str]]:
        rows: list[list[str]] = []
        base = Decimal("100") if symbol == "BTCUSDT" else Decimal("110")
        start_ms = 1_700_000_000_000
        for index in range(18):
            open_price = base + (Decimal(str(index)) * Decimal("0.05"))
            close_price = open_price + Decimal("0.02")
            high = close_price + Decimal("0.02")
            low = open_price - Decimal("0.02")
            rows.append([
                str(start_ms + (index * 60000)),
                str(open_price),
                str(high),
                str(low),
                str(close_price),
                "100",
            ])
        previous_open = base + Decimal("0.90")
        previous_close = previous_open + Decimal("0.03")
        previous_high = previous_close + Decimal("0.02")
        previous_low = previous_open - Decimal("0.02")
        rows.append([
            str(start_ms + (18 * 60000)),
            str(previous_open),
            str(previous_high),
            str(previous_low),
            str(previous_close),
            "100",
        ])
        latest_open = previous_close
        latest_close = previous_high + Decimal("0.20")
        latest_high = latest_close + Decimal("0.02")
        latest_low = latest_open - Decimal("0.05")
        rows.append([
            str(start_ms + (19 * 60000)),
            str(latest_open),
            str(latest_high),
            str(latest_low),
            str(latest_close),
            "160",
        ])
        return list(reversed(rows))

    @staticmethod
    def _bearish_rows(symbol: str) -> list[list[str]]:
        rows: list[list[str]] = []
        base = Decimal("90")
        start_ms = 1_700_000_000_000
        for index in range(18):
            open_price = base - (Decimal(str(index)) * Decimal("0.04"))
            close_price = open_price - Decimal("0.02")
            high = open_price + Decimal("0.02")
            low = close_price - Decimal("0.02")
            rows.append([
                str(start_ms + (index * 60000)),
                str(open_price),
                str(high),
                str(low),
                str(close_price),
                "100",
            ])
        previous_open = Decimal("89.20")
        previous_close = previous_open - Decimal("0.03")
        previous_high = previous_open + Decimal("0.02")
        previous_low = previous_close - Decimal("0.02")
        rows.append([
            str(start_ms + (18 * 60000)),
            str(previous_open),
            str(previous_high),
            str(previous_low),
            str(previous_close),
            "100",
        ])
        latest_open = previous_close
        latest_close = previous_low - Decimal("0.20")
        latest_high = latest_open + Decimal("0.05")
        latest_low = latest_close - Decimal("0.02")
        rows.append([
            str(start_ms + (19 * 60000)),
            str(latest_open),
            str(latest_high),
            str(latest_low),
            str(latest_close),
            "160",
        ])
        return list(reversed(rows))


class DoubleDownPhase12Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.persistence = InMemoryPersistence()
        self.bybit = FakeBybitService()
        self.service = ChallengeService(self.persistence, bybit_service=self.bybit)
        created = self.service.create(
            starting_balance=Decimal("100"),
            failure_floor=Decimal("20"),
        )
        self.challenge_id = UUID(created["config"]["challenge_id"])
        self.service.start(self.challenge_id)

    def test_run_cycle_executes_and_persists_active_cycle(self):
        snapshot = self.service.run_cycle(self.challenge_id)

        self.assertEqual(snapshot["state"]["status"], "cycle_active")
        self.assertEqual(snapshot["state"]["cycle_number"], 1)
        self.assertGreater(snapshot["state"]["active_trade_count"], 0)
        self.assertIsNotNone(snapshot["runtime"]["active_cycle"])
        self.assertEqual(snapshot["runtime"]["last_cycle"]["status"], "cycle_active")
        self.assertTrue(all(item["status"] == "protected" for item in snapshot["runtime"]["active_cycle"]["execution_results"]))

    def test_finalize_cycle_closes_positions_and_records_pnl(self):
        active_snapshot = self.service.run_cycle(self.challenge_id)
        expected_closes = len(active_snapshot["runtime"]["active_cycle"]["active_trades"])

        snapshot = self.service.finalize_cycle(self.challenge_id)

        self.assertIn(snapshot["state"]["status"], {"running", "recovery", "completed", "failed"})
        self.assertEqual(snapshot["state"]["active_trade_count"], 0)
        self.assertIsNone(snapshot["runtime"]["active_cycle"])
        self.assertIsNotNone(snapshot["runtime"]["last_cycle"]["finalization"])
        self.assertEqual(len(self.bybit.close_calls), expected_closes)

    def test_finalize_cycle_requires_active_cycle(self):
        with self.assertRaisesRegex(ValueError, "no active cycle"):
            self.service.finalize_cycle(self.challenge_id)


if __name__ == "__main__":
    unittest.main()
