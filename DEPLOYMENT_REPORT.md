# Deployment Readiness Report

## Runtime crash cause

`artifacts/crypto-dashboard/vite.config.ts` required Replit-injected `PORT` and `BASE_PATH` at module load and threw immediately when either variable was absent. Local Vite and Vercel therefore failed before the app could start. The Replit runtime error overlay only displayed the failure; it was not the root cause.

The configuration now defaults to port `5173` and base path `/`, while still accepting environment overrides.

## Files changed

- `artifacts/api-server/app/core/config.py`
- `artifacts/api-server/app/main.py`
- `artifacts/api-server/start.sh`
- `artifacts/api-server/.env.example`
- `artifacts/crypto-dashboard/vite.config.ts`
- `artifacts/crypto-dashboard/src/api/client.ts`
- `artifacts/crypto-dashboard/package.json`
- `artifacts/crypto-dashboard/.env.example`
- `package.json`
- `pnpm-lock.yaml`
- `scripts/preinstall.mjs`
- `render.yaml`
- `vercel.json`
- `DEPLOYMENT.md`

No strategy, risk, scanner, signal, execution, or trading module was changed.

## Validation

Passed:

- Python compile check for the FastAPI application.
- Backend config assertions for `PORT`, CORS origins, `/health`, and `/api/health`.
- Backend startup through `start.sh` using an environment-provided port.
- HTTP smoke checks for `/health` and `/api/health`.
- CORS preflight check for a configured Vercel origin.
- JSON and YAML configuration parsing.
- TypeScript syntax validation for all 76 frontend TypeScript/TSX files.
- Cross-platform Node preinstall guard validation.

Not available in the project:

- Backend automated tests.
- Frontend lint script.
- Frontend test script.

Frontend production build was attempted, but this execution environment has no installed pnpm/dependencies and cannot access the npm registry. Corepack failed on DNS resolution before the project build could start. Vercel has the required install/build commands in `vercel.json`.

## Render environment

- `APP_ENV=production`
- `FRONTEND_URL=https://your-project.vercel.app`
- `CORS_ORIGINS=https://your-project.vercel.app`
- `DEFAULT_SYSTEM_MODE=demo`
- `DEFAULT_STRATEGY_MODE=scalping`
- `BYBIT_ENV=demo`
- `BYBIT_BASE_URL=https://api-demo.bybit.com`
- `BYBIT_DEMO_API_KEY`
- `BYBIT_DEMO_API_SECRET`

Render supplies `PORT` automatically.

## Vercel environment

- `VITE_API_BASE_URL=https://your-render-service.onrender.com/api`

`BASE_PATH` is optional and defaults to `/`.
