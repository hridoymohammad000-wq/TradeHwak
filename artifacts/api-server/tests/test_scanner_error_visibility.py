import unittest

from app.core.enums import Direction, SignalGrade, Timeframe, TradingMode
from app.schemas.scanner import ScanRequest
from app.services.scanner_service import ScannerService
from app.services.strategy_service import StrategyEvaluation, StrategySignal


class FakeSettingsService:
    def get_mode_summary(self):
        class Response:
            class Data:
                active_strategy_mode = TradingMode.SCALPING

            data = Data()

        return Response()


class FakeSignalRegistry:
    def __init__(self):
        self.replaced = None

    def replace(self, mode, signals, source):
        self.replaced = (mode, signals, source)


class FakeStrategyService:
    def default_symbols(self, mode):
        return ["BTCUSDT"]

    def default_timeframe(self, mode):
        return Timeframe.M5

    def evaluate_symbol_detailed(self, symbol, mode, timeframe):
        outcomes = {
            "BTCUSDT": StrategyEvaluation(
                symbol="BTCUSDT",
                outcome="actionable",
                signal=StrategySignal(
                    symbol="BTCUSDT",
                    mode=TradingMode.SCALPING,
                    timeframe=Timeframe.M5,
                    direction=Direction.BUY,
                    grade=SignalGrade.A_PLUS,
                    status="armed",
                    entry_price=100.0,
                    current_price=100.0,
                    reason="ready",
                    metrics={"final_score": 95.0},
                ),
            ),
            "ETHUSDT": StrategyEvaluation(
                symbol="ETHUSDT",
                outcome="rejected",
                detail="No valid setup.",
            ),
            "SOLUSDT": StrategyEvaluation(
                symbol="SOLUSDT",
                outcome="exchange_error",
                detail="Bybit request failed",
            ),
            "XRPUSDT": StrategyEvaluation(
                symbol="XRPUSDT",
                outcome="insufficient_data",
                detail="Need more candles.",
            ),
            "ADAUSDT": StrategyEvaluation(
                symbol="ADAUSDT",
                outcome="failed",
                detail="Unexpected parser error",
            ),
        }
        return outcomes[symbol]


class ScannerErrorVisibilityTests(unittest.TestCase):
    def test_scan_reports_breakdown_and_issue_details(self):
        service = ScannerService(
            settings_service=FakeSettingsService(),
            strategy_service=FakeStrategyService(),
            signal_registry=FakeSignalRegistry(),
        )

        response = service.scan(
            payload=ScanRequest(
                mode=TradingMode.SCALPING,
                symbols=[
                    "BTCUSDT",
                    "ETHUSDT",
                    "SOLUSDT",
                    "XRPUSDT",
                    "ADAUSDT",
                    "BTCUSDT",
                ],
                timeframe=Timeframe.M5,
            )
        )

        self.assertEqual(response.data.breakdown.scanned, 5)
        self.assertEqual(response.data.breakdown.actionable, 1)
        self.assertEqual(response.data.breakdown.rejected, 1)
        self.assertEqual(response.data.breakdown.skipped, 1)
        self.assertEqual(response.data.breakdown.exchange_error, 1)
        self.assertEqual(response.data.breakdown.insufficient_data, 1)
        self.assertEqual(response.data.breakdown.failed, 1)
        self.assertEqual([result.symbol for result in response.data.results], ["BTCUSDT"])
        self.assertEqual(
            {(issue.symbol, issue.status) for issue in response.data.issues},
            {
                ("ETHUSDT", "rejected"),
                ("SOLUSDT", "exchange_error"),
                ("XRPUSDT", "insufficient_data"),
                ("ADAUSDT", "failed"),
                ("BTCUSDT", "skipped"),
            },
        )


if __name__ == "__main__":
    unittest.main()
