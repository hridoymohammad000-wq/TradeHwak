# Crypto Scalping Trader

A crypto scalping and intraday trading dashboard with a FastAPI Python backend (Bybit demo integration) and a React/Vite frontend.

## Run & Operate

- `bash artifacts/api-server/start.sh` — run the Python FastAPI backend (port 8080, served at `/api`)
- `pnpm --filter @workspace/crypto-dashboard run dev` — run the React frontend (served at `/`)
- Workflows manage both automatically — use the Replit workflow panel to restart them

## Stack

- **Backend**: FastAPI 0.139, Pydantic 2.13, Uvicorn 0.49 (Python 3.13)
- **Frontend**: React 19, Vite 7, Tailwind CSS v4, Framer Motion 12
- **Routing**: Replit path proxy — `/api/*` → Python backend, `/` → React frontend

## Where things live

- `artifacts/api-server/app/` — FastAPI source (routes, services, schemas, core)
- `artifacts/api-server/.venv/` — Python virtualenv (gitignored, created on first start)
- `artifacts/api-server/start.sh` — startup script (creates venv, installs deps, runs uvicorn)
- `artifacts/crypto-dashboard/src/` — React source
- `artifacts/crypto-dashboard/src/api/client.ts` — API client (base URL resolves via `window.location.origin + /api`)
- `artifacts/crypto-dashboard/src/components/pages/` — 7 pages: Dashboard, Scanner, Signals, Chart, Active Trades, Journal, Settings

## Architecture decisions

- Python backend runs under `/api` prefix via `app.include_router(api_router, prefix="/api")` so Replit's path proxy routes correctly without URL rewriting.
- Frontend API client defaults `API_BASE_URL` to `/api` and converts it to an absolute URL at runtime using `window.location.origin` (required because `new URL()` needs an absolute base).
- Python deps isolated in `.venv/` (not the Nix system) to work around Nix's immutable store restriction.
- CORS set to `allow_origins=["*"]` with `allow_credentials=False` — same-origin via proxy makes CORS redundant, but permissive config avoids dev issues.
- `framer-motion` (catalog entry `^12.23.24`) used instead of the separate `motion` package since the catalog already pins the correct version and both export the same API.

## Environment Secrets

Set these in Replit Secrets for Bybit connectivity:

| Secret | Description |
|--------|-------------|
| `BYBIT_DEMO_API_KEY` | Bybit demo account API key |
| `BYBIT_DEMO_API_SECRET` | Bybit demo account API secret |
| `SESSION_SECRET` | Already configured |

Without Bybit keys the app runs in demo mode with placeholder data.

## Product

Dashboard with 7 sections:
- **Dashboard** — live market snapshot (BTC price, 24h change, spread), engine status, recent events
- **Scanner** — market scan by mode/timeframe/direction/grade
- **Signals** — active trading signals with filters
- **Chart Workspace** — chart context and indicator readings (EMA20/50/200, RSI)
- **Active Trades** — open scalping and intraday positions
- **Operator Journal** — closed trade history
- **Control Center** — full settings: system/strategy mode, risk params, engine toggles, notifications, Bybit connection test

## User preferences

_Populate as you build._

## Gotchas

- Run `pnpm run typecheck` from workspace root to check TS across all packages.
- The Python backend venv is at `artifacts/api-server/.venv/` — if it gets corrupted, delete it and restart the workflow.
- `start.sh` re-runs `pip install` on every boot (quiet mode) to pick up any requirements changes.
- Do NOT change `info.title` in `lib/api-spec/openapi.yaml` — it controls generated filenames.

## Pointers

- See `pnpm-workspace` skill for workspace structure and TypeScript setup.
- Bybit service lives in `artifacts/api-server/app/services/bybit_service.py`.
- Trading engine loop runs every 15s via `_auto_trade_loop()` in `app/main.py`.
