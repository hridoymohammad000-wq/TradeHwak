# TradeHawk Trading Workspace

TradeHawk is a React/Vite trading terminal with a Python FastAPI backend for Bybit Demo Trading.

## Canonical deployment architecture

The repository currently contains two Python backend directories, but only one is the deployed source of truth:

- `artifacts/api-server/` — **canonical backend used by Render**
- `backend/` — legacy/non-deployed implementation retained temporarily for controlled comparison only
- repository root — React/Vite frontend

The deployment path is defined by `render.yaml`:

- backend root directory: `artifacts/api-server`
- build command: `pip install -r requirements.txt`
- start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- health endpoint: `/health`

Do not implement production backend changes in `backend/`. Do not copy complete files between the two backends because their routing, persistence, authentication, service wiring, and execution flows are different.

## Canonical backend behavior

The active FastAPI application:

- exposes `GET /health` at the root;
- exposes application routes under `/api`;
- reads settings and trade history through `PersistenceRepository`;
- uses PostgreSQL when `DATABASE_URL` is configured;
- reloads persisted settings, workflow state, active trades, closed trades, and executed signal identifiers;
- treats settings as the single source of truth for engine and auto-trade readiness;
- persists the latest scanner, signal, and execution workflow snapshot.

Auto trade is considered execution-ready only when all of these are true:

- system mode is Demo;
- emergency stop is off;
- auto trade is enabled;
- the currently selected strategy engine is enabled;
- risk per trade is above zero;
- max open positions is above zero;
- daily max trades is above zero.

Bybit connection and remaining risk capacity are checked separately before an order can be submitted.

## Backend development

Work from the canonical directory:

```bash
cd artifacts/api-server
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Run backend tests from the same directory:

```bash
python -m unittest discover -s tests
```

## Frontend development

The frontend lives at the repository root:

```bash
npm install
npm run dev
```

Production verification:

```bash
npm run lint
npm run build
```

The frontend API base URL must point to the canonical Render backend and use the `/api` route prefix for application endpoints.
