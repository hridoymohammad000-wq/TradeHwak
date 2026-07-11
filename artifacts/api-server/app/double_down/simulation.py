from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.double_down.engine import ChallengeEngine
from app.double_down.enums import ChallengeDirection, ChallengeStatus
from app.double_down.market_data import ClosedCandle
from app.double_down.risk import PositionSizeResult


@dataclass(frozen=True)
class SimulatedTradeResult:
    symbol: str
    outcome: str
    exit_price: Decimal
    gross_pnl: Decimal
    fees: Decimal
    slippage: Decimal
    net_pnl: Decimal
    bars_held: int


@dataclass(frozen=True)
class SimulationReport:
    starting_balance: Decimal
    ending_balance: Decimal
    target_balance: Decimal
    cycles_completed: int
    wins: int
    losses: int
    unresolved: int
    gross_pnl: Decimal
    fees: Decimal
    slippage: Decimal
    net_pnl: Decimal
    final_status: ChallengeStatus
    max_drawdown: Decimal
    balance_path: tuple[Decimal, ...]


def simulate_position(
    *,
    symbol: str,
    direction: ChallengeDirection,
    position: PositionSizeResult,
    future_candles: list[ClosedCandle],
    taker_fee_rate_per_side: Decimal = Decimal("0.00055"),
    slippage_rate: Decimal = Decimal("0.00050"),
) -> SimulatedTradeResult:
    if not position.approved:
        raise ValueError("simulation requires an approved position size")
    if not future_candles:
        raise ValueError("future_candles cannot be empty")
    if taker_fee_rate_per_side < 0 or slippage_rate < 0:
        raise ValueError("fee and slippage rates cannot be negative")

    normalized = symbol.strip().upper()
    ordered = sorted(future_candles, key=lambda item: item.close_time)
    if any(item.symbol.strip().upper() != normalized for item in ordered):
        raise ValueError("all simulation candles must match the position symbol")
    if len({item.close_time for item in ordered}) != len(ordered):
        raise ValueError("duplicate simulation candles are not allowed")

    exit_price: Decimal | None = None
    outcome = "unresolved"
    bars_held = 0

    for index, candle in enumerate(ordered, start=1):
        bars_held = index
        if direction == ChallengeDirection.LONG:
            stop_hit = candle.low <= position.stop_loss
            take_hit = candle.high >= position.take_profit
        else:
            stop_hit = candle.high >= position.stop_loss
            take_hit = candle.low <= position.take_profit

        # Conservative deterministic rule: when both levels are touched in the same
        # candle, assume the stop was reached first. No optimistic intrabar ordering.
        if stop_hit:
            outcome = "loss"
            exit_price = position.stop_loss
            break
        if take_hit:
            outcome = "win"
            exit_price = position.take_profit
            break

    if exit_price is None:
        exit_price = ordered[-1].close

    if direction == ChallengeDirection.LONG:
        gross_pnl = (exit_price - position.entry_price) * position.quantity
    else:
        gross_pnl = (position.entry_price - exit_price) * position.quantity

    entry_notional = position.entry_price * position.quantity
    exit_notional = exit_price * position.quantity
    fees = (entry_notional + exit_notional) * taker_fee_rate_per_side
    slippage = (entry_notional + exit_notional) * slippage_rate
    net_pnl = gross_pnl - fees - slippage

    return SimulatedTradeResult(
        symbol=normalized,
        outcome=outcome,
        exit_price=exit_price,
        gross_pnl=gross_pnl,
        fees=fees,
        slippage=slippage,
        net_pnl=net_pnl,
        bars_held=bars_held,
    )


def build_simulation_report(
    *,
    engine: ChallengeEngine,
    cycle_results: list[list[SimulatedTradeResult]],
) -> SimulationReport:
    if engine.state.status == ChallengeStatus.DRAFT:
        engine.mark_ready()
        engine.start()
    elif engine.state.status == ChallengeStatus.READY:
        engine.start()
    elif engine.state.status not in {ChallengeStatus.RUNNING, ChallengeStatus.RECOVERY}:
        raise ValueError("engine must be ready, running, or recovery before simulation")

    starting_balance = engine.state.current_balance
    path = [starting_balance]
    wins = losses = unresolved = 0
    gross = fees = slippage = Decimal("0")
    peak = starting_balance
    max_drawdown = Decimal("0")
    completed_cycles = 0

    for cycle_number, results in enumerate(cycle_results, start=1):
        if engine.state.status in {
            ChallengeStatus.COMPLETED,
            ChallengeStatus.FAILED,
            ChallengeStatus.TERMINATED,
        }:
            break
        if not results or len(results) > engine.config.max_active_trades:
            raise ValueError("each simulation cycle must contain between 1 and 3 trades")

        engine.activate_cycle(len(results))
        cycle_price_pnl = Decimal("0")
        cycle_costs = Decimal("0")
        for result in results:
            gross += result.gross_pnl
            fees += result.fees
            slippage += result.slippage
            cycle_price_pnl += result.gross_pnl
            cycle_costs += result.fees + result.slippage
            if result.outcome == "win":
                wins += 1
            elif result.outcome == "loss":
                losses += 1
            else:
                unresolved += 1

        engine.close_cycle(
            net_pnl=cycle_price_pnl,
            fees=cycle_costs,
            reference_id=f"simulation-cycle-{cycle_number}",
        )
        completed_cycles += 1
        balance = engine.state.current_balance
        path.append(balance)
        peak = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)

    return SimulationReport(
        starting_balance=starting_balance,
        ending_balance=engine.state.current_balance,
        target_balance=engine.config.target_balance,
        cycles_completed=completed_cycles,
        wins=wins,
        losses=losses,
        unresolved=unresolved,
        gross_pnl=gross,
        fees=fees,
        slippage=slippage,
        net_pnl=engine.state.current_balance - starting_balance,
        final_status=engine.state.status,
        max_drawdown=max_drawdown,
        balance_path=tuple(path),
    )
