# Double Down Challenge V1 — Release Checklist

## Release classification

- Code status: release candidate after all CI checks pass.
- Allowed execution modes: paper and demo only.
- Live-money execution: prohibited and not represented by the exchange-mode enum.
- Normal TradeHawk engine remains separate; challenge tables, state, risk and execution paths must not mutate normal TradeHawk balances or trades.

## Mandatory pre-deployment evidence

1. All backend unit and contract tests pass.
2. Frontend production build passes.
3. `DATABASE_URL` is configured and the database is reachable.
4. `double_down_challenges` migration succeeds without modifying existing TradeHawk trade or journal tables.
5. A database backup exists and a restore has been tested in a non-production environment.
6. Demo smoke test verifies create → start → pause → resume → terminate and restart rehydration.
7. Demo execution verifies deterministic client order IDs, SL/TP confirmation and emergency close after repeated protection failure.
8. Rollback to the previous verified commit has been rehearsed.

## Deployment order

1. Take and verify a database backup.
2. Deploy backend release candidate.
3. Verify health endpoint and database initialization.
4. Verify challenge API read/write and restart recovery.
5. Deploy frontend.
6. Run authenticated UI smoke test.
7. Keep live mode blocked.

## Smoke-test acceptance criteria

- Challenge creation persists a distinct challenge ID.
- Starting balance, target, state and ledger survive backend restart.
- Challenge API never exposes or accepts a live execution mode.
- A failed protection attachment triggers one retry and then an emergency reduce-only close.
- Repeating an execution request reuses the deterministic client order ID instead of creating a duplicate.
- Normal TradeHawk active trades, journal and account balance are unchanged by challenge-only actions.

## Rollback plan

1. Stop challenge activity and confirm no demo challenge position is left unprotected.
2. Roll back backend and frontend to the previous verified commit.
3. Do not drop `double_down_challenges`; the additive table may remain for forward recovery.
4. Verify TradeHawk health, login, dashboard, active trades and journal.
5. Record the incident and release-blocking evidence.

## Production approval gate

A successful deploy is not proof of functional readiness. Approval requires database reachability, backup/restore evidence, demo smoke-test evidence and rollback evidence. Until all four are recorded, the release is code-ready only and must not be described as production-ready.
