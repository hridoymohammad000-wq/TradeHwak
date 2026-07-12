import unittest
from types import SimpleNamespace

from app.core.enums import Direction, SignalGrade, Timeframe, TradingMode
from app.schemas.scanner import ScanRequest
from app.services.auto_trade_service import AutoTradeService
from app.services.scanner_service import ScannerService
from app.services.signals_service import SignalsService
from app.services.strategy_service import StrategyEvaluation, StrategySignal
from app.services.trade_service import TradeService


class FakeSettings:
    def __init__(self):
        self.updated_controls = None

    def get_settings_state(self):
        return SimpleNamespace(
            auto_trade_enabled=True,
            daily_max_trades=5,
            daily_max_loss=100.0,
            scalping_engine_enabled=True,
            intraday_engine_enabled=False,
            active_strategy_mode=TradingMode.SCALPING,
            allowed_signal_grades=[SignalGrade.A_PLUS, SignalGrade.A],
        )

    def get_execution_readiness(self):
        return True, None

    def update_control_state(self, controls):
        self.updated_controls = controls
        return None

    def get_mode_summary(self):
        return SimpleNamespace(data=SimpleNamespace(active_strategy_mode=TradingMode.SCALPING))


class FakeBybit:
    def get_connection_status(self):
        return SimpleNamespace(data=SimpleNamespace(code="CONNECTED", detail="ok"))


class FakeTradeService:
    def sync_with_exchange(self, bybit_service):
        return None

    def get_daily_trade_count(self):
        return 0

    def get_remaining_daily_loss_budget(self, configured):
        return configured

    def get_active_trades(self):
        data = SimpleNamespace(scalping_trades=[], intraday_trades=[])
        return SimpleNamespace(data=data)

    def has_open_trade_for_symbol(self, symbol):
        return False

    def get_open_trade_count(self):
        return 0

    def build_signal_id(self, **kwargs):
        return TradeService.build_signal_id(**kwargs)


class FakeSignalRegistry:
    def __init__(self):
        self.replacements = []

    def replace(self, mode, signals, source):
        self.replacements.append((mode, [signal.symbol for signal in signals], source))

    def get(self, mode):
        return []


class FakeRepository:
    def __init__(self):
        self.logs = []

    def verify_execution_ready(self):
        return True, None

    def load_workflow_state(self):
        return None

    def save_workflow_state(self, state):
        self.state = state

    def append_log(self, table, event_type, payload):
        self.logs.append((table, event_type, payload))


class RankedStrategyService:
    def default_timeframe(self, mode):
        return Timeframe.M5

    def default_symbols(self, mode):
        return ["LOWUSDT", "HIGHUSDT", "ERRUSDT"]

    def evaluate_symbol_detailed(self, symbol, mode, timeframe):
        if symbol == "ERRUSDT":
            return StrategyEvaluation(
                symbol=symbol,
                outcome="exchange_error",
                detail="Bybit request failed",
            )
        score = 91.0 if symbol == "HIGHUSDT" else 85.0
        return StrategyEvaluation(
            symbol=symbol,
            outcome="actionable",
            signal=StrategySignal(
                symbol=symbol,
                mode=mode,
                timeframe=timeframe,
                direction=Direction.BUY,
                grade=SignalGrade.A_PLUS if symbol == "HIGHUSDT" else SignalGrade.A,
                status="armed",
                entry_price=100.0,
                current_price=100.0,
                reason="ready",
                metrics={"final_score": score, "setup_timestamp": 1784000000000 + int(score)},
            ),
        )


class RecordingManualTrade:
    def __init__(self):
        self.executed_symbols = []

    def execute_strategy_trade(self, **kwargs):
        self.executed_symbols.append(kwargs["symbol"])
        return SimpleNamespace(
            data=SimpleNamespace(
                symbol=kwargs["symbol"],
                side="Buy",
                qty="1",
                order_id=f"ord-{kwargs['symbol']}",
                status="submitted",
            )
        )


class TradingEngineBatchTests(unittest.TestCase):
    def test_auto_trade_ranks_before_execution_and_logs_auto_scan_breakdown(self):
        manual_trade = RecordingManualTrade()
        repository = FakeRepository()
        registry = FakeSignalRegistry()
        service = AutoTradeService(
            settings_service=FakeSettings(),
            bybit_service=FakeBybit(),
            strategy_service=RankedStrategyService(),
            manual_trade_service=manual_trade,
            trade_service=FakeTradeService(),
            signal_registry=registry,
            repository=repository,
        )

        result = service.run_cycle()

        self.assertEqual(result, {"status": "executed", "opened": 2})
        self.assertEqual(manual_trade.executed_symbols[0], "HIGHUSDT")
        self.assertEqual(registry.replacements[0][1], ["HIGHUSDT", "LOWUSDT"])
        scan_log = next(
            payload
            for table, event_type, payload in repository.logs
            if table == "scan_logs" and event_type == "auto_scan_cycle_completed"
        )
        self.assertEqual(scan_log["breakdown"]["actionable"], 2)
        self.assertEqual(scan_log["breakdown"]["exchange_error"], 1)
        self.assertIn("actionable=2", service._last_scanner_status)

    def test_signals_service_uses_setup_timestamp_in_signal_id(self):
        registry = FakeSignalRegistry()
        registry.get = lambda mode: [
            StrategySignal(
                symbol="BTCUSDT",
                mode=TradingMode.SCALPING,
                timeframe=Timeframe.M5,
                direction=Direction.BUY,
                grade=SignalGrade.A_PLUS,
                status="armed",
                entry_price=100.0,
                current_price=100.0,
                reason="ready",
                metrics={"final_score": 95.0, "atr14": 1.0, "swing_low": 98.0, "higher_timeframe_score": 5.0, "setup_timestamp": 1784001234567},
            )
        ]
        service = SignalsService(
            settings_service=FakeSettings(),
            strategy_service=RankedStrategyService(),
            signal_registry=registry,
        )

        response = service.get_signals(TradingMode.SCALPING, None, None, None)

        signal_id = response.data.signals[0].signal_id
        self.assertIn("1784001234567", signal_id)
        self.assertTrue(signal_id.endswith(str(__import__("app.core.trading_clock", fromlist=["trading_date"]).trading_date().isoformat())))

    def test_signal_id_changes_for_different_setup_timestamps(self):
        first = TradeService.build_signal_id(
            symbol="BTCUSDT",
            timeframe=Timeframe.M5,
            direction=Direction.BUY,
            setup_timestamp=1784000000000,
        )
        second = TradeService.build_signal_id(
            symbol="BTCUSDT",
            timeframe=Timeframe.M5,
            direction=Direction.BUY,
            setup_timestamp=1784000009999,
        )

        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
