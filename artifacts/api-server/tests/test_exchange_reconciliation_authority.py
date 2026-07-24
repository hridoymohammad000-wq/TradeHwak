import unittest

from app.core.enums import Direction, TradingMode
from app.services.settings_service import SettingsService
from app.services.trade_service import TradeService


class MemoryRepository:
    def __init__(self):
        self.settings = None
        self.trades = {}
        self.journal = {}
        self.signal_ids = set()

    def load_settings(self):
        return self.settings

    def save_settings(self, settings):
        self.settings = settings

    def load_trade_state(self):
        active = []
        closed = []
        for status, payload in self.trades.values():
            if status == "closed":
                closed.append(payload)
            else:
                active.append(payload)
        return active, closed

    def upsert_trade(self, trade_key, status, payload):
        self.trades[trade_key] = (status, payload)

    def save_journal_entry(self, trade_key, payload):
        self.journal[trade_key] = payload

    def delete_trade(self, trade_key):
        self.trades.pop(trade_key, None)

    def delete_journal_entry(self, trade_key):
        self.journal.pop(trade_key, None)

    def load_executed_signal_ids(self, trade_day):
        return set(self.signal_ids)

    def save_executed_signal_id(self, signal_id, trade_day):
        self.signal_ids.add(signal_id)

    def append_log(self, table, event_type, payload):
        return None


class FakeBybit:
    def get_open_positions(self):
        return []

    def get_closed_pnls(self, limit=100):
        return [
            {
                "symbol": "LABUSDT",
                "side": "Sell",
                "qty": "178",
                "avgEntryPrice": "0.929",
                "avgExitPrice": "0.759",
                "closedPnl": "29.6696",
                "orderId": "lab-close-2",
                "createdTime": "1783750000000",
                "updatedTime": "1783751000000",
            },
            {
                "symbol": "LABUSDT",
                "side": "Sell",
                "qty": "297",
                "avgEntryPrice": "0.929",
                "avgExitPrice": "0.844",
                "closedPnl": "24.6922",
                "orderId": "lab-close-1",
                "createdTime": "1783740000000",
                "updatedTime": "1783741000000",
            },
            {
                "symbol": "1000PEPEUSDT",
                "side": "Buy",
                "qty": "451800",
                "avgEntryPrice": "0.002825",
                "avgExitPrice": "0.002814",
                "closedPnl": "-6.3710",
                "orderId": "pepe-close-1",
                "createdTime": "1783730000000",
                "updatedTime": "1783731000000",
            },
        ]


class OppositeSideBybit:
    def get_open_positions(self):
        return [
            {
                "symbol": "BTCUSDT",
                "side": "Sell",
                "positionIdx": 0,
                "size": "0.010",
                "avgPrice": "65000",
                "markPrice": "64950",
                "stopLoss": "65200",
                "takeProfit": "64500",
                "createdTime": "1783750000000",
                "updatedTime": "1783751000000",
            }
        ]

    def get_closed_pnls(self, limit=100):
        return []


class ExchangeReconciliationAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.repository = MemoryRepository()
        self.settings = SettingsService(repository=self.repository)
        self.service = TradeService(
            settings_service=self.settings,
            repository=self.repository,
        )

    def test_exchange_open_positions_are_authoritative_and_stale_trade_closes(self):
        self.service.register_open_trade(
            symbol="1000PEPEUSDT",
            mode=TradingMode.INTRADAY,
            direction=Direction.BUY,
            entry_price=0.002825,
            stop_loss=0.00280,
            take_profit=0.002875,
            timeframe=None,
            order_id="local-pepe-open",
            qty="451800",
        )

        self.service.sync_with_exchange(FakeBybit())

        response = self.service.get_active_trades()
        self.assertEqual(response.data.today_summary.total_open_trades, 0)
        self.assertIn("local-pepe-open", self.repository.journal)
        self.assertEqual(
            self.repository.journal["local-pepe-open"]["realized_pnl"],
            -6.371,
        )

    def test_multiple_closes_for_same_symbol_are_preserved(self):
        self.service.sync_with_exchange(FakeBybit())

        lab_records = [
            row
            for row in self.service.get_closed_trades().data.closed_trades
            if row.symbol == "LABUSDT"
        ]
        self.assertEqual(len(lab_records), 2)
        self.assertEqual(
            {round(row.realized_pnl or 0, 4) for row in lab_records},
            {29.6696, 24.6922},
        )
        self.assertEqual(
            {row.direction for row in lab_records},
            {Direction.BUY},
        )

        pepe_record = next(
            row
            for row in self.service.get_closed_trades().data.closed_trades
            if row.symbol == "1000PEPEUSDT"
        )
        self.assertEqual(pepe_record.direction, Direction.SELL)

    def test_refresh_is_idempotent(self):
        self.service.sync_with_exchange(FakeBybit())
        first_count = len(self.service.get_closed_trades().data.closed_trades)
        first_journal_count = len(self.repository.journal)

        self.service.sync_with_exchange(FakeBybit())

        self.assertEqual(
            len(self.service.get_closed_trades().data.closed_trades),
            first_count,
        )
        self.assertEqual(len(self.repository.journal), first_journal_count)

    def test_imported_trade_mode_is_restored_from_history(self):
        self.service.register_open_trade(
            symbol="LABUSDT",
            mode=TradingMode.SCALPING,
            direction=Direction.BUY,
            entry_price=0.929,
            stop_loss=0.90,
            take_profit=1.0,
            timeframe=None,
            qty="178",
        )
        self.service._active_trades.clear()
        self.service.reload_from_persistence()

        self.service.sync_with_exchange(FakeBybit())

        lab_records = [
            row
            for row in self.service.get_closed_trades().data.closed_trades
            if row.symbol == "LABUSDT"
        ]
        self.assertTrue(lab_records)
        self.assertEqual({row.mode for row in lab_records}, {TradingMode.SCALPING})

    def test_open_position_matching_does_not_use_symbol_only(self):
        self.service.register_open_trade(
            symbol="BTCUSDT",
            mode=TradingMode.SCALPING,
            direction=Direction.BUY,
            entry_price=65010.0,
            stop_loss=64800.0,
            take_profit=65400.0,
            timeframe=None,
            order_id="btc-long-open",
            qty="0.010",
        )

        self.service.sync_with_exchange(OppositeSideBybit())

        active = self.service.get_active_trades().data
        self.assertEqual(active.today_summary.total_open_trades, 1)
        imported = active.intraday_trades + active.scalping_trades
        self.assertEqual(len(imported), 1)
        self.assertEqual(imported[0].direction, Direction.SELL)

    def test_duplicate_closed_rows_are_deduped_and_richer_record_wins(self):
        imported_only = {
            "symbol": "LABUSDT",
            "mode": "intraday",
            "direction": "sell",
            "external_id": "exchange-closed:lab-close-1",
            "qty": "297",
            "entry_price": 0.929,
            "exit_price": 0.844,
            "stop_loss": 0.0,
            "take_profit": 0.0,
            "notional": 275.913,
            "planned_risk_usdt": None,
            "realized_pnl": 24.6922,
            "risk_reward": None,
            "result": "win",
            "status": "closed_on_exchange",
            "close_reason": "profit_exit",
            "exit_analysis": "Imported exchange close.",
            "timeframe": None,
            "opened_at": "2026-07-10T10:00:00+00:00",
            "closed_time": "2026-07-10T10:16:40+00:00",
        }
        richer = {
            **imported_only,
            "stop_loss": 0.90,
            "take_profit": 1.0,
            "planned_risk_usdt": 8.72,
            "risk_reward": 2.0,
            "timeframe": "M5",
            "exit_analysis": "Tracked managed trade close.",
        }
        self.repository.trades["exchange-closed:lab-close-1"] = ("closed", imported_only)
        self.repository.trades["local-lab-open"] = ("closed", richer)

        self.service.reload_from_persistence()

        closed = self.service.get_closed_trades().data.closed_trades
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].symbol, "LABUSDT")
        self.assertEqual(closed[0].risk_reward, 2.0)
        self.assertEqual(closed[0].timeframe.value, "M5")


if __name__ == "__main__":
    unittest.main()
