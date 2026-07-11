import asyncio
import unittest
from decimal import Decimal
from threading import Event, Lock, Thread
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app import main
from app.core.enums import TradingMode
from app.core.trading_clock import trading_date, trading_now
from app.services.auto_trade_service import AutoTradeService
from app.services.managed_auto_trade_service import ManagedAutoTradeService
from app.services.managed_manual_trade_service import ManagedManualTradeService
from app.services.manual_trade_service import ManualTradeService
from app.services.trade_service import TradeService


class LimitTradeService:
    def __init__(self, *, daily_count=0, scalping_count=0, intraday_count=0):
        self.daily_count = daily_count
        self.scalping_count = scalping_count
        self.intraday_count = intraday_count

    def sync_with_exchange(self, bybit_service):
        return None

    def was_signal_executed(self, signal_id):
        return False

    def has_open_trade_for_symbol(self, symbol):
        return False

    def get_daily_trade_count(self):
        return self.daily_count

    def get_active_trades(self):
        data = SimpleNamespace(
            scalping_trades=[object()] * self.scalping_count,
            intraday_trades=[object()] * self.intraday_count,
        )
        return SimpleNamespace(data=data)


class ManagementSpy:
    def __init__(self):
        self.calls = 0

    def manage_open_trades(self):
        self.calls += 1
        return {"skipped": 0}


class EngineWorkflowSafetyTests(unittest.TestCase):
    @staticmethod
    def settings(*, daily_max_trades=5, max_open_positions=5):
        return SimpleNamespace(
            daily_max_trades=daily_max_trades,
            max_open_positions=max_open_positions,
        )

    @staticmethod
    def managed_manual(trade_service, settings):
        service = ManagedManualTradeService.__new__(ManagedManualTradeService)
        service._trade_service = trade_service
        service._bybit_service = object()
        service._settings_service = SimpleNamespace(
            get_settings_state=lambda: settings
        )
        return service

    def test_daily_trade_limit_blocks_before_order_submission(self):
        service = self.managed_manual(
            LimitTradeService(daily_count=3),
            self.settings(daily_max_trades=3),
        )
        payload = SimpleNamespace(symbol="BTCUSDT", mode=TradingMode.SCALPING)

        with self.assertRaises(HTTPException) as context:
            service.execute_manual_trade(payload)

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("Daily trade limit of 3 reached", context.exception.detail)

    def test_zero_max_open_positions_blocks_instead_of_falling_back(self):
        service = self.managed_manual(
            LimitTradeService(),
            self.settings(max_open_positions=0),
        )
        payload = SimpleNamespace(symbol="BTCUSDT", mode=TradingMode.SCALPING)

        with self.assertRaises(HTTPException) as context:
            service.execute_manual_trade(payload)

        self.assertEqual(context.exception.status_code, 409)
        self.assertIn("Overall open-position limit of 0 reached", context.exception.detail)

    def test_daily_loss_budget_caps_new_trade_risk(self):
        service = ManualTradeService.__new__(ManualTradeService)
        service._trade_service = SimpleNamespace(
            get_remaining_daily_loss_budget=lambda configured: 25.0
        )

        approved = service._apply_daily_loss_guard(Decimal("50"), 100.0)

        self.assertEqual(approved, Decimal("25.0"))

    def test_exhausted_daily_loss_budget_blocks_new_trade(self):
        service = ManualTradeService.__new__(ManualTradeService)
        service._trade_service = SimpleNamespace(
            get_remaining_daily_loss_budget=lambda configured: 0.0
        )

        with self.assertRaises(HTTPException) as context:
            service._apply_daily_loss_guard(Decimal("50"), 100.0)

        self.assertIn("Daily max loss limit reached", context.exception.detail)

    def test_trade_service_calculates_net_daily_loss_budget(self):
        service = TradeService.__new__(TradeService)
        service._trade_day = trading_date()
        service._closed_trades = [
            SimpleNamespace(
                closed_time=trading_now().isoformat(),
                realized_pnl=-30.0,
            ),
            SimpleNamespace(
                closed_time=trading_now().isoformat(),
                realized_pnl=5.0,
            ),
        ]
        service._ensure_current_day = lambda: None

        self.assertEqual(service.get_daily_realized_loss(), 25.0)
        self.assertEqual(service.get_remaining_daily_loss_budget(100.0), 75.0)

    def test_concurrent_cycle_is_rejected(self):
        service = AutoTradeService.__new__(AutoTradeService)
        service._cycle_lock = Lock()
        entered = Event()
        release = Event()
        first_result = []

        def slow_cycle():
            entered.set()
            release.wait(timeout=2)
            return {"status": "executed", "opened": 1}

        service._run_cycle = slow_cycle
        worker = Thread(target=lambda: first_result.append(service.run_cycle()))
        worker.start()
        self.assertTrue(entered.wait(timeout=1))

        second_result = service.run_cycle()
        release.set()
        worker.join(timeout=2)

        self.assertEqual(second_result, {"status": "already_running", "opened": 0})
        self.assertEqual(first_result, [{"status": "executed", "opened": 1}])

    def test_management_does_not_run_for_rejected_concurrent_cycle(self):
        service = ManagedAutoTradeService.__new__(ManagedAutoTradeService)
        service._cycle_lock = Lock()
        service._cycle_lock.acquire()
        management = ManagementSpy()
        service._trade_management_service = management

        try:
            result = service.run_cycle()
        finally:
            service._cycle_lock.release()

        self.assertEqual(result["status"], "already_running")
        self.assertEqual(management.calls, 0)


class BackgroundCycleSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_background_cycle_is_offloaded_from_event_loop(self):
        result = {"status": "idle", "opened": 0}
        to_thread = AsyncMock(return_value=result)
        sleep = AsyncMock(side_effect=asyncio.CancelledError)

        with (
            patch.object(main.asyncio, "to_thread", to_thread),
            patch.object(main.asyncio, "sleep", sleep),
            patch.object(main.persistence_repository, "append_log"),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await main._auto_trade_loop()

        to_thread.assert_awaited_once_with(main.auto_trade_service.run_cycle)


if __name__ == "__main__":
    unittest.main()
