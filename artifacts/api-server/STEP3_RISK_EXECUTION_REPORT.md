# Step 3 — Risk + Execution Integration

Implemented:

- Daily 5% target does not pause new trades.
- Once a dynamic daily profit floor exists, every manual and automatic order is checked before submission.
- Worst-case new risk is limited to the realized-profit cushion above the locked floor.
- Existing open-trade planned risk is deducted from the available cushion.
- New order quantity is reduced when only partial risk capacity remains.
- New execution is rejected when the locked floor has no remaining risk capacity.
- The normal configured per-trade risk remains unchanged before the first lock level is reached.
- Risk decisions are written to execution logs with configured budget, approved budget, floor, cushion, and rejection reason.
- Auto trading continues through the existing signal-quality, duplicate-signal, open-symbol, capacity, and daily-trade guards.

The enforcement is located in `ManualTradeService`, so the same protection applies to both manual orders and strategy-generated automatic orders.

Verification added in `tests/test_step3_risk_execution.py`.
