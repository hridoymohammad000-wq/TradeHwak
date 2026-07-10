import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from app.core.enums import Direction, Timeframe, TradingMode
from app.schemas.trades import ClosedTradeRecord
from app.services.settings_service import SettingsService
from app.services.trade_service import ManagedTrade, TradeService


class DayScopedRepository:
    def __init__(self):
        self.signal_ids_by_day = {}

    def load_settings(self):
        return None

    def save_settings(self, settings):
        return None

    def load_executed_signal_ids(self, trade_day):
        return set(self.signal_ids_by_day.get(trade_day, set()))

    def save_executed_signal_id(self, signal_id, trade_day):
        self.signal_ids_by_day.setdefault(trade_day, set()).add(signal_id)

    def upsert_trade(self, trade_key, status, payload):
        return None


class StepOneDayRolloverTests(unittest.TestCase):
    def make_service(self, trade_day=date(2026, 7, 10)):
        repository = DayScopedRepository()
        with patch("app.services.trade_service.trading_date", return_value=trade_day):
            service = TradeService(SettingsService(repository=repository), repository)
        return service, repository

    def test_bdt_midnight_rollover_resets_day_scoped_state_only(self):
        service, repository = self.make_service()
        carry = ManagedTrade(
            symbol="BTCUSDT",
            mode=TradingMode.SCALPING,
            direction=Direction.BUY,
            entry_price=100.0,
            current_price=101.0,
            stop_loss=99.0,
            take_profit=102.0,
            pnl=1.0,
            timeframe=Timeframe.M5,
            status="open",
            opened_at="2026-07-10T17:30:00+00:00",
        )
        service._active_trades = [carry]
        service._closed_trades = [
            ClosedTradeRecord(
                symbol="ETHUSDT",
                mode=TradingMode.SCALPING,
                direction=Direction.BUY,
                status="closed_on_exchange",
                opened_at="2026-07-10T12:00:00+00:00",
                closed_time="2026-07-10T17:45:00+00:00",
            )
        ]
        service._executed_signal_ids = {"old-signal"}
        repository.signal_ids_by_day[date(2026, 7, 11)] = {"new-day-signal"}

        with patch("app.services.trade_service.trading_date", return_value=date(2026, 7, 11)):
            service._ensure_current_day()

        self.assertEqual(service._trade_day, date(2026, 7, 11))
        self.assertEqual(service._executed_signal_ids, {"new-day-signal"})
        self.assertEqual(len(service._active_trades), 1)
        self.assertEqual(len(service._closed_trades), 1)
        with patch("app.services.trade_service.trading_date", return_value=date(2026, 7, 11)):
            self.assertEqual(service.get_daily_trade_count(), 0)

    def test_daily_count_uses_entry_date_not_close_date(self):
        service, _ = self.make_service(date(2026, 7, 11))
        service._active_trades = [
            ManagedTrade(
                symbol="BTCUSDT",
                mode=TradingMode.SCALPING,
                direction=Direction.BUY,
                entry_price=100.0,
                current_price=101.0,
                stop_loss=99.0,
                take_profit=102.0,
                pnl=1.0,
                timeframe=Timeframe.M5,
                status="open",
                opened_at="2026-07-10T18:15:00+00:00",
            )
        ]
        service._closed_trades = [
            ClosedTradeRecord(
                symbol="ETHUSDT",
                mode=TradingMode.INTRADAY,
                direction=Direction.SELL,
                status="closed_on_exchange",
                opened_at="2026-07-10T16:00:00+00:00",
                closed_time="2026-07-10T19:00:00+00:00",
            ),
            ClosedTradeRecord(
                symbol="SOLUSDT",
                mode=TradingMode.SCALPING,
                direction=Direction.BUY,
                status="closed_on_exchange",
                opened_at="2026-07-10T18:30:00+00:00",
                closed_time="2026-07-10T19:30:00+00:00",
            ),
        ]

        service._recalculate_daily_trade_count()
        with patch("app.services.trade_service.trading_date", return_value=date(2026, 7, 11)):
            self.assertEqual(service.get_daily_trade_count(), 2)

    def test_signal_id_uses_bdt_trading_date(self):
        with patch("app.services.trade_service.trading_date", return_value=date(2026, 7, 11)):
            signal_id = TradeService.build_signal_id(
                symbol="BTCUSDT",
                timeframe=Timeframe.M5,
                direction=Direction.BUY,
            )
        self.assertTrue(signal_id.endswith("2026-07-11"))

    def test_register_open_trade_uses_utc_timestamp_but_bdt_day_scope(self):
        service, _ = self.make_service(date(2026, 7, 11))
        now_bdt = datetime(2026, 7, 11, 0, 5, tzinfo=timezone.utc).astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Dhaka")
        )
        with patch("app.services.trade_service.trading_date", return_value=date(2026, 7, 11)), patch(
            "app.services.trade_service.trading_now", return_value=now_bdt
        ):
            service.register_open_trade(
                symbol="BTCUSDT",
                mode=TradingMode.SCALPING,
                direction=Direction.BUY,
                entry_price=100.0,
                stop_loss=99.0,
                take_profit=102.0,
                timeframe=Timeframe.M5,
                signal_id="sig-1",
            )
        with patch("app.services.trade_service.trading_date", return_value=date(2026, 7, 11)):
            self.assertEqual(service.get_daily_trade_count(), 1)
        self.assertTrue(service._active_trades[0].opened_at.endswith("+00:00"))


if __name__ == "__main__":
    unittest.main()
