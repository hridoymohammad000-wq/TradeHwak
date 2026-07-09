import unittest
from decimal import Decimal

from app.core.enums import Direction, TradingMode
from app.services.auto_trade_service import AutoTradeService
from app.services.manual_trade_service import ManualTradeService
from app.services.settings_service import SettingsService
from app.services.signal_registry import SignalRegistry
from app.services.trade_service import TradeService


class MemoryRepository:
    def __init__(self):
        self.settings = None
        self.logs = []
        self.trades = {}
        self.signal_ids = set()

    def load_settings(self):
        return self.settings

    def save_settings(self, settings):
        self.settings = settings

    def append_log(self, table, event_type, payload):
        self.logs.append((table, event_type, payload))

    def upsert_trade(self, trade_key, status, payload):
        self.trades[trade_key] = (status, payload)

    def save_journal_entry(self, trade_key, payload):
        return None

    def load_executed_signal_ids(self, trade_day):
        return set(self.signal_ids)

    def save_executed_signal_id(self, signal_id, trade_day):
        self.signal_ids.add(signal_id)


class FakeBybitPositions:
    def get_open_positions(self):
        return [
            {
                "symbol": "BTCUSDT",
                "side": "Buy",
                "size": "0.01",
                "avgPrice": "60000",
                "markPrice": "60500",
                "stopLoss": "59000",
                "takeProfit": "62000",
                "unrealisedPnl": "5",
                "createdTime": "1783500000000",
                "positionIdx": 0,
            }
        ]

    def get_closed_pnls(self, limit=50):
        return []


class StepTwoWorkflowTests(unittest.TestCase):
    def test_risk_reward_minimum(self):
        rr = ManualTradeService._risk_reward(
            Direction.BUY,
            Decimal("100"),
            Decimal("99"),
            Decimal("102"),
        )
        self.assertEqual(rr, Decimal("2"))

    def test_partial_manual_protection_is_rejected(self):
        service = ManualTradeService.__new__(ManualTradeService)
        with self.assertRaises(Exception) as context:
            service._resolve_protection_prices(
                direction=Direction.BUY,
                mode=TradingMode.SCALPING,
                timeframe=None,
                market_price=Decimal("100"),
                stop_loss=99.0,
                take_profit=None,
            )
        self.assertIn("Provide both stop loss", str(context.exception))

    def test_untracked_exchange_position_is_imported(self):
        repository = MemoryRepository()
        settings = SettingsService(repository=repository)
        trades = TradeService(settings_service=settings, repository=repository)

        trades.sync_with_exchange(FakeBybitPositions())
        response = trades.get_active_trades()

        self.assertEqual(response.data.today_summary.total_open_trades, 1)
        record = response.data.scalping_trades[0]
        self.assertEqual(record.symbol, "BTCUSDT")
        self.assertEqual(record.status, "exchange_open_untracked")
        self.assertEqual(record.planned_risk_usdt, 10.0)

    def test_exact_http_detail_is_preserved(self):
        detail = AutoTradeService._format_http_detail(
            {"retCode": 110007, "retMsg": "Available balance is insufficient"}
        )
        self.assertEqual(
            detail,
            "Bybit code 110007: Available balance is insufficient",
        )

    def test_signal_registry_shares_latest_scan(self):
        registry = SignalRegistry()
        registry.replace(TradingMode.SCALPING, [], source="test")
        self.assertEqual(registry.get(TradingMode.SCALPING), [])
        self.assertIsNotNone(registry.updated_at(TradingMode.SCALPING))


if __name__ == "__main__":
    unittest.main()
