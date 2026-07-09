# Canonical TradeHawk backend

This directory contains the FastAPI backend deployed by Render.

Deployment contract:

- root directory: `artifacts/api-server`
- install: `pip install -r requirements.txt`
- start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- health check: `/health`
- application API prefix: `/api`

Active runtime components:

- `app/`
- `migrations/`
- `requirements.txt`
- `start.sh`

Persistence uses `PersistenceRepository`. When `DATABASE_URL` is configured, startup initializes the schema and reloads settings, workflow state, trade history, and executed signal identifiers.

Execution readiness is derived from persisted settings. A static build flag is not used as the operator-facing execution status.

The separate repository-level `backend/` directory is a legacy/non-deployed implementation. Do not copy its files into this backend without an architecture compatibility review.
