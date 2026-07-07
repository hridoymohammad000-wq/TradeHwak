# Supabase/Postgres Persistence Report

## Scope

Added backend persistence without modifying strategy, scanner, signal, risk, execution, or Command Center orchestration logic.

## Persisted state

- Runtime bot settings
- Open and closed trade history
- Closed-trade journal entries
- Scanner request/result logs
- Signal fetch/result logs
- Manual order and auto-trade cycle execution logs
- Daily executed signal IDs for restart-safe duplicate prevention

## Fallback

When `DATABASE_URL` is absent, all database methods are safe no-ops and the original process-memory behavior remains available.
