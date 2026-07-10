# Step 2 — Profit Tracking + Dynamic Profit Lock

Implemented and locally verified:

- Daily realized PnL and return percentage in BDT trading-day scope.
- Weekly realized PnL and return percentage using Monday–Sunday BDT scope.
- Daily and weekly peak return tracking.
- Daily target 5% and weekly target 30% metadata.
- Dynamic daily profit-lock ladder: 7% peak → 5% lock, 10% → 7%, 13% → 10%, then +3% lock per completed +3% peak step.
- Profit lock and peak values never decrease during the same trading day.
- Daily state resets at BDT midnight while weekly state is preserved until the next week.
- Persistent restoration after restart.
- Dashboard profit-tracking payload.

Verification: 21/21 backend unit tests passed locally.

Step 2 tracks and persists the floor. Risk/execution enforcement of the floor belongs to Step 3.
