import unittest
from threading import Lock

from app.core.enums import Direction, Timeframe, TradingMode
from app.services.auto_trade_service import AutoTradeService
from app.services.manual_trade_service import ManualTradeService


class LockingRepository:
    def __init__(self, acquired=True):
        self.acquired = acquired
        self.unlock_calls = 0
        self.lock_calls = 0

    def try_advisory_lock(self, name):
        self.lock_calls += 1
        return self.acquired

    def advisory_unlock(self, name):
        self.unlock_calls += 1
        return True


class DuplicateExecutionSafetyTests(unittest.TestCase):
    def test_distributed_cycle_lock_blocks_duplicate_worker_execution(self):
        repository = LockingRepository(acquired=False)
        service = AutoTradeService.__new__(AutoTradeService)
        service._repository = repository
        service._cycle_lock = Lock()

        result = service.run_cycle()

        self.assertEqual(result, {"status": "already_running", "opened": 0})
        self.assertEqual(repository.lock_calls, 1)
        self.assertEqual(repository.unlock_calls, 0)

    def test_distributed_cycle_lock_is_released_after_successful_cycle(self):
        repository = LockingRepository(acquired=True)
        service = AutoTradeService.__new__(AutoTradeService)
        service._repository = repository
        service._cycle_lock = Lock()
        service._run_cycle = lambda: {"status": "executed", "opened": 1}

        result = service.run_cycle()

        self.assertEqual(result, {"status": "executed", "opened": 1})
        self.assertEqual(repository.lock_calls, 1)
        self.assertEqual(repository.unlock_calls, 1)

    def test_distributed_cycle_lock_is_released_after_cycle_failure(self):
        repository = LockingRepository(acquired=True)
        service = AutoTradeService.__new__(AutoTradeService)
        service._repository = repository
        service._cycle_lock = Lock()

        def boom():
            raise RuntimeError("cycle failed")

        service._run_cycle = boom

        with self.assertRaises(RuntimeError):
            service.run_cycle()

        self.assertEqual(repository.lock_calls, 1)
        self.assertEqual(repository.unlock_calls, 1)

    def test_order_link_id_reuses_signal_identity_for_idempotency(self):
        first = ManualTradeService._order_link_id(
            symbol="BTCUSDT",
            mode=TradingMode.SCALPING,
            direction=Direction.BUY,
            timeframe=Timeframe.M1,
            signal_id="sig-btcusdt-m1-buy-2026-07-12",
        )
        second = ManualTradeService._order_link_id(
            symbol="BTCUSDT",
            mode=TradingMode.SCALPING,
            direction=Direction.BUY,
            timeframe=Timeframe.M1,
            signal_id="sig-btcusdt-m1-buy-2026-07-12",
        )

        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 36)


if __name__ == "__main__":
    unittest.main()
