import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.double_down.engine import ChallengeEngine
from app.double_down.enums import ChallengeDirection, ChallengeStatus
from app.double_down.market_data import ClosedCandle
from app.double_down.risk import PositionSizeResult
from app.double_down.simulation import (
    SimulatedTradeResult,
    build_simulation_report,
    simulate_position,
)


class DoubleDownPhase7SimulationTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc)

    def position(self, *, entry="100", stop="90", take="110", quantity="1"):
        entry_d = Decimal(entry)
        stop_d = Decimal(stop)
        take_d = Decimal(take)
        quantity_d = Decimal(quantity)
        return PositionSizeResult(
            approved=True,
            rejection_code=None,
            quantity=quantity_d,
            entry_price=entry_d,
            stop_loss=stop_d,
            take_profit=take_d,
            stop_distance=abs(entry_d - stop_d),
            gross_risk=abs(entry_d - stop_d) * quantity_d,
            estimated_fees=Decimal("0"),
            estimated_slippage=Decimal("0"),
            total_estimated_loss=abs(entry_d - stop_d) * quantity_d,
            notional=entry_d * quantity_d,
            slot_risk_budget=Decimal("10"),
            evidence={},
        )

    def candle(self, minute, *, symbol="BTCUSDT", open="100", high="101", low="99", close="100"):
        open_time = self.start + timedelta(minutes=minute)
        return ClosedCandle(
            symbol=symbol,
            open_time=open_time,
            close_time=open_time + timedelta(minutes=1),
            open=Decimal(open),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            volume=Decimal("100"),
        )

    def engine(self):
        return ChallengeEngine.create(
            starting_balance=Decimal("100"),
            failure_floor=Decimal("20"),
            created_at=self.start,
        )

    def test_long_take_profit_is_simulated(self):
        result = simulate_position(
            symbol="BTCUSDT",
            direction=ChallengeDirection.LONG,
            position=self.position(),
            future_candles=[
                self.candle(1, high="105", low="95", close="103"),
                self.candle(2, high="111", low="102", close="109"),
            ],
            taker_fee_rate_per_side=Decimal("0"),
            slippage_rate=Decimal("0"),
        )
        self.assertEqual(result.outcome, "win")
        self.assertEqual(result.exit_price, Decimal("110"))
        self.assertEqual(result.gross_pnl, Decimal("10"))
        self.assertEqual(result.bars_held, 2)

    def test_same_candle_stop_and_target_uses_conservative_stop(self):
        result = simulate_position(
            symbol="BTCUSDT",
            direction=ChallengeDirection.LONG,
            position=self.position(),
            future_candles=[self.candle(1, high="111", low="89", close="105")],
            taker_fee_rate_per_side=Decimal("0"),
            slippage_rate=Decimal("0"),
        )
        self.assertEqual(result.outcome, "loss")
        self.assertEqual(result.exit_price, Decimal("90"))

    def test_short_take_profit_is_simulated(self):
        result = simulate_position(
            symbol="ETHUSDT",
            direction=ChallengeDirection.SHORT,
            position=self.position(entry="100", stop="110", take="90", quantity="2"),
            future_candles=[self.candle(1, symbol="ETHUSDT", high="101", low="89", close="92")],
            taker_fee_rate_per_side=Decimal("0"),
            slippage_rate=Decimal("0"),
        )
        self.assertEqual(result.outcome, "win")
        self.assertEqual(result.gross_pnl, Decimal("20"))

    def test_unresolved_trade_closes_at_last_candle_and_deducts_costs(self):
        result = simulate_position(
            symbol="BTCUSDT",
            direction=ChallengeDirection.LONG,
            position=self.position(),
            future_candles=[self.candle(1, high="105", low="95", close="102")],
            taker_fee_rate_per_side=Decimal("0.001"),
            slippage_rate=Decimal("0.001"),
        )
        self.assertEqual(result.outcome, "unresolved")
        self.assertEqual(result.exit_price, Decimal("102"))
        self.assertLess(result.net_pnl, result.gross_pnl)
        self.assertEqual(result.net_pnl, result.gross_pnl - result.fees - result.slippage)

    def test_report_tracks_recovery_balance_and_drawdown(self):
        report = build_simulation_report(
            engine=self.engine(),
            cycle_results=[
                [
                    SimulatedTradeResult(
                        symbol="BTCUSDT",
                        outcome="loss",
                        exit_price=Decimal("90"),
                        gross_pnl=Decimal("-30"),
                        fees=Decimal("1"),
                        slippage=Decimal("1"),
                        net_pnl=Decimal("-32"),
                        bars_held=1,
                    )
                ],
                [
                    SimulatedTradeResult(
                        symbol="BTCUSDT",
                        outcome="win",
                        exit_price=Decimal("110"),
                        gross_pnl=Decimal("20"),
                        fees=Decimal("1"),
                        slippage=Decimal("1"),
                        net_pnl=Decimal("18"),
                        bars_held=1,
                    )
                ],
            ],
        )
        self.assertEqual(report.ending_balance, Decimal("86"))
        self.assertEqual(report.final_status, ChallengeStatus.RECOVERY)
        self.assertEqual(report.max_drawdown, Decimal("32"))
        self.assertEqual(report.balance_path, (Decimal("100"), Decimal("68"), Decimal("86")))
        self.assertEqual(report.cycles_completed, 2)

    def test_report_stops_after_completion(self):
        report = build_simulation_report(
            engine=self.engine(),
            cycle_results=[
                [
                    SimulatedTradeResult(
                        symbol="BTCUSDT",
                        outcome="win",
                        exit_price=Decimal("200"),
                        gross_pnl=Decimal("100"),
                        fees=Decimal("0"),
                        slippage=Decimal("0"),
                        net_pnl=Decimal("100"),
                        bars_held=1,
                    )
                ],
                [
                    SimulatedTradeResult(
                        symbol="ETHUSDT",
                        outcome="loss",
                        exit_price=Decimal("90"),
                        gross_pnl=Decimal("-10"),
                        fees=Decimal("0"),
                        slippage=Decimal("0"),
                        net_pnl=Decimal("-10"),
                        bars_held=1,
                    )
                ],
            ],
        )
        self.assertEqual(report.final_status, ChallengeStatus.COMPLETED)
        self.assertEqual(report.cycles_completed, 1)
        self.assertEqual(report.ending_balance, Decimal("200"))

    def test_mixed_symbols_are_rejected(self):
        with self.assertRaises(ValueError):
            simulate_position(
                symbol="BTCUSDT",
                direction=ChallengeDirection.LONG,
                position=self.position(),
                future_candles=[self.candle(1, symbol="ETHUSDT")],
            )


if __name__ == "__main__":
    unittest.main()
