# Step 4 — Strategy Brain + Trade Management

Implemented:

- Separate scalping and intraday scoring policies.
- Scalping uses 5m entries with 1h alignment, tighter extension limits and liquidity/volume emphasis.
- Intraday uses 15m entries with 4h alignment and mandatory EMA200 direction alignment.
- Executable grades are A+ (90+) and A (85–89.99); lower grades are not returned for execution.
- TP1 at 2R closes 50% of original quantity and moves SL to entry.
- TP2 at 3R closes another 30% and moves SL to the 2R level.
- Remaining 20% uses one-risk-distance trailing; stops can only tighten.
- Partial orders are reduce-only IOC orders with deterministic orderLinkId values.
- Order and stop submissions retry once.
- Management stages persist across restarts to prevent repeated TP submissions.
- Closed positions are removed from management state.
- Regression tests cover grade thresholds, mode separation, EMA200 alignment, R-multiple calculation, one-way stop movement and deterministic order IDs.

Verification status: code and branch diff inspected. Runtime tests require a Python environment or GitHub Actions and are not claimed as executed in this connector session.
