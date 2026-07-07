# Render Backend + Vercel Frontend Deployment

## Render backend

Use the repository root with the included `render.yaml`, or create a Python Web Service with:

- Root directory: `artifacts/api-server`
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

Required Render environment variables:

- `APP_ENV=production`
- `FRONTEND_URL=https://your-vercel-project.vercel.app`
- `CORS_ORIGINS=https://your-vercel-project.vercel.app` (comma-separated when more than one frontend origin is required)
- `DEFAULT_SYSTEM_MODE=demo`
- `DEFAULT_STRATEGY_MODE=scalping`
- `BYBIT_ENV=demo`
- `BYBIT_BASE_URL=https://api-demo.bybit.com`
- `BYBIT_DEMO_API_KEY=<secret>`
- `BYBIT_DEMO_API_SECRET=<secret>`

Render supplies `PORT`; do not hardcode it.

## Vercel frontend

Deploy from the repository root with the included `vercel.json`:

- Install command: `pnpm --filter @workspace/crypto-dashboard... install --frozen-lockfile`
- Build command: `pnpm --filter @workspace/crypto-dashboard build`
- Output directory: `artifacts/crypto-dashboard/dist/public`

Required Vercel environment variable:

- `VITE_API_BASE_URL=https://your-render-service.onrender.com/api`

Optional:

- `BASE_PATH=/` (already defaults to `/`)

After Vercel creates the final production domain, add that exact domain to both `FRONTEND_URL` and `CORS_ORIGINS` on Render, then redeploy the backend.

## Local development

Backend:

```bash
cd artifacts/api-server
python3 -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend, from the repository root:

```bash
pnpm install --frozen-lockfile
pnpm --filter @workspace/crypto-dashboard dev
```

The Vite development server defaults to port `5173` and proxies `/api` to `http://127.0.0.1:8000`. To bypass the proxy, copy `artifacts/crypto-dashboard/.env.example` to `.env` and set `VITE_API_BASE_URL` directly.

Health endpoints:

- Render health check: `GET /health`
- Existing API health endpoint: `GET /api/health`

## Supabase/Postgres persistence

The backend uses the standard Postgres connection string in `DATABASE_URL`. No Bybit API key or secret is written to the database.

1. Create or open a Supabase project.
2. In Supabase, open **Project Settings → Database → Connection string**.
3. Copy the Postgres URI. For a long-running Render service, use the direct connection or Supabase session-pooler URI. Keep SSL enabled as supplied by Supabase.
4. Add the URI to Render as the secret environment variable `DATABASE_URL`.
5. Deploy the backend. On startup it safely runs `artifacts/api-server/migrations/001_init.sql` using `CREATE TABLE IF NOT EXISTS`.

Created tables:

- `bot_settings`
- `trade_history`
- `journal`
- `scan_logs`
- `signal_logs`
- `execution_logs`
- `executed_signal_ids`

`executed_signal_ids` is reloaded on startup for the current trading day, preventing the same generated signal ID from being executed again after a backend restart.

### Local fallback

`DATABASE_URL` is optional for local development. When it is missing, the repository becomes a no-op and the existing in-memory behavior remains active. A database connection or write failure is logged but does not stop the API from starting or serving requests.

To test locally with Postgres, add this to `artifacts/api-server/.env`:

```env
DATABASE_URL=postgresql://postgres:password@host:5432/postgres?sslmode=require
```
