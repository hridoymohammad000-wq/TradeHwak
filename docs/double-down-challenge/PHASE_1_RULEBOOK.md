# Double Down Challenge — Phase 1 Rulebook

## 1. Purpose

Build a fully isolated, high-risk challenge engine that attempts to grow a user-defined challenge balance to 2x its starting value through short-term crypto scalping.

This module must not share balance, risk state, active-trade state, or persistence records with the normal TradeHawk engine.

## 2. Initial Scope

- Exchange target: Binance USD-M Futures demo/paper first
- Runtime: Python
- Timeframe: 1-minute closed candles only
- Maximum simultaneous trades: 3
- Risk–Reward ratio: 1:1
- Challenge target: starting balance × 2
- Starting balance: user-defined
- Live trading: prohibited until local simulation, backtest, demo execution, and safety testing pass

## 3. Fixed Trading Slots

The engine maintains three independent candidate slots:

1. BTC Anchor Slot
   - Symbol fixed to BTCUSDT
   - Direction selected by strategy evidence

2. Top Gainer Slot
   - Select one eligible symbol from the 24-hour top-gainer universe
   - Must pass liquidity, spread, volume, candle-quality, and strategy filters

3. Top Loser Slot
   - Select one eligible symbol from the 24-hour top-loser universe
   - Must pass liquidity, spread, volume, candle-quality, and strategy filters

Rules:

- Maximum one active trade per slot
- No duplicate symbol across slots
- Direction is never inferred only from gainer/loser classification
- Every trade requires closed-candle confirmation and a valid strategy decision

## 4. Risk Model

Default challenge configuration:

- Total cycle risk: 30% of current challenge balance
- Per-slot risk: total cycle risk ÷ approved trade count
- Maximum approved trades per cycle: 3
- Risk–Reward: exactly 1:1 in V1
- Fees and estimated slippage must be deducted from expected net result
- Position quantity must be calculated from stop distance, not from a fixed notional amount

Example with 100 USDT:

- Total cycle risk: 30 USDT
- Three approved trades: 10 USDT risk each
- Maximum gross cycle result: approximately +30 or -30 USDT before fees/slippage

## 5. Loss Replanning

After each completed cycle:

- Reconcile all realized PnL and fees
- Set current challenge balance to the reconciled ledger balance
- Recalculate total cycle risk from the new balance
- Recalculate per-slot risk from the number of approved slots
- Recalculate quantity using the new risk budget and stop distance

Example:

- Starting balance: 100
- Cycle result: -30
- New balance: 70
- New total cycle risk: 21
- Three approved trades: 7 risk each

If balance falls below the original starting balance, the engine enters Recovery Mode. The immediate recovery target becomes the original starting balance. After recovery, the challenge target remains starting balance × 2.

## 6. Challenge State Machine

Allowed states:

- DRAFT
- READY
- RUNNING
- CYCLE_ACTIVE
- REPLANNING
- RECOVERY
- PAUSED
- COMPLETED
- FAILED
- TERMINATED

Core transitions:

- DRAFT -> READY after configuration validation
- READY -> RUNNING by explicit user start
- RUNNING -> CYCLE_ACTIVE when at least one protected trade opens
- CYCLE_ACTIVE -> REPLANNING after all cycle trades close
- REPLANNING -> RECOVERY when balance is below starting balance
- REPLANNING -> RUNNING when balance is at or above starting balance but below target
- REPLANNING -> COMPLETED when reconciled balance reaches or exceeds target and no positions remain open
- Any active state -> PAUSED on safety failure or user pause
- Any non-terminal state -> TERMINATED by explicit user termination
- Any active state -> FAILED when the configured failure condition is reached

## 7. Completion and Failure

Completed when:

- Reconciled net balance reaches or exceeds target balance
- No challenge positions remain open
- Fees and final trade records are reconciled
- Final ledger is locked

Failed when one of the following applies:

- Balance reaches the configured failure floor
- Available balance cannot support the minimum valid protected order
- An unrecoverable exchange/account mismatch occurs
- Repeated protection or execution failures exceed the configured threshold
- User explicitly ends the challenge as failed

Terminal behavior:

- Block new orders
- Reconcile open and recently closed positions
- Generate final summary
- Persist immutable terminal state

## 8. Safety Invariants

- Main TradeHawk balance and risk data must never be modified
- No order may remain without confirmed SL and TP protection
- Failed protection attachment requires emergency close
- No duplicate symbol positions
- No duplicate cycle/order submission
- Open positions must be reconciled against the exchange before every new cycle
- Stale or incomplete 1-minute candles must be rejected
- Unknown exchange positions must pause the challenge
- Database write failure must pause the challenge
- No fake market data in simulation modes labelled as real/demo exchange modes

## 9. Planned Python Modules

- challenge_controller.py
- challenge_state_machine.py
- challenge_market_data.py
- challenge_symbol_selector.py
- challenge_strategy.py
- challenge_risk.py
- challenge_execution.py
- challenge_trade_manager.py
- challenge_ledger.py
- challenge_watchdog.py

## 10. Planned Data Models

### ChallengeConfig

- challenge_id
- starting_balance
- target_balance
- failure_floor
- cycle_risk_pct
- max_active_trades
- timeframe
- rr_ratio
- exchange_mode
- created_at

### ChallengeState

- challenge_id
- status
- current_balance
- recovery_target
- cycle_number
- active_trade_count
- last_replanned_at
- completed_at
- failed_at

### ChallengeSlot

- slot_type
- selected_symbol
- direction
- confidence
- strategy_name
- rejection_reason
- approved_risk
- status

### ChallengeTrade

- challenge_trade_id
- challenge_id
- cycle_number
- slot_type
- symbol
- direction
- entry_price
- stop_loss
- take_profit
- quantity
- planned_risk
- gross_pnl
- fees
- net_pnl
- opened_at
- closed_at
- close_reason

### ChallengeLedgerEntry

- entry_id
- challenge_id
- cycle_number
- entry_type
- balance_before
- amount
- balance_after
- reference_id
- created_at

## 11. Planned API Contract

- POST /api/challenge
- GET /api/challenge/{challenge_id}
- POST /api/challenge/{challenge_id}/start
- POST /api/challenge/{challenge_id}/pause
- POST /api/challenge/{challenge_id}/resume
- POST /api/challenge/{challenge_id}/terminate
- POST /api/challenge/{challenge_id}/reset
- GET /api/challenge/{challenge_id}/slots
- GET /api/challenge/{challenge_id}/trades
- GET /api/challenge/{challenge_id}/ledger
- GET /api/challenge/{challenge_id}/report

No endpoint may execute live orders during Phase 1.

## 12. Phase 1 Exit Criteria

Phase 1 is complete only when:

- All business rules are documented
- State transitions are unambiguous
- Risk formulas are explicit
- Symbol-slot rules are explicit
- Completion/failure conditions are explicit
- Data models are defined
- API boundaries are defined
- Main engine isolation is explicitly documented
- No live/demo execution code has been added
