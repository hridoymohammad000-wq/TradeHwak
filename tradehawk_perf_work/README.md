# TradeHawk Trading Workspace

TradeHawk is a private React/TypeScript trading terminal backed by the canonical FastAPI application in `/backend`. The application is locked to Bybit Demo Trading and uses one backend-only access token to create an authenticated browser session.

## Architecture

- `/backend` — the only FastAPI backend and source of truth for trade identifiers, status, timestamps, mode, PnL, and journal summaries
- `src/api/client.ts` — the only frontend HTTP client; handles base URL, credentials, timeouts, JSON parsing, normalized API errors, authentication, and the connected Dashboard/Active Trades/Journal requests
- `src/context/AuthContext.tsx` — authentication, session refresh, expiry, and backend connection state
- `src/context/AppContext.tsx` — shared canonical Dashboard, Active Trades, and Journal state
- `src/pages/Login.tsx` — single Access Token login screen
- `src/api/services.ts` — UI-only data helpers for pages that are intentionally not backend-wired in this phase (Scanner, Signals, Chart, and Control Center)

## Connected real-data endpoints

Authenticated frontend requests use the shared client and these canonical backend endpoints:

- `GET /dashboard-summary?start_time=<ISO>&end_time=<ISO>`
- `GET /active-trades?start_time=<ISO>&end_time=<ISO>`
- `GET /closed-trades?start_time=<ISO>&end_time=<ISO>`

Dashboard, Active Trades, and Journal display only backend-returned records. Their default range is the current local day. Journal also supports explicit date/time ranges. Persisted `scalping` and `intraday` values are displayed directly; legacy records without a stored mode are shown as `Unknown` and are never inferred from timeframe, strategy, or UI labels.

Journal summaries are calculated in the backend for Scalping, Intraday, Unknown, and Combined records. Metrics that cannot be supported by the persisted source fields are returned as unavailable and displayed as `N/A`.

## Private access setup

Create `backend/.env` from `backend/.env.example` and set a unique token of at least 32 characters:

```env
TRADEHAWK_ACCESS_TOKEN=<private-random-token>
```

The real token must remain only in `backend/.env` or the deployment platform's secret manager. It must never be added to frontend variables, source control, logs, or build output.

Create a root `.env` from `.env.example` with the public backend URL only:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The frontend sends the token once to `POST /auth/login`. The backend validates it using constant-time comparison and returns an opaque `HttpOnly` session cookie. The token is not stored in localStorage, sessionStorage, cookies, or API responses.

## Authentication behavior

- `GET /health` is public so the frontend can report real backend availability.
- `POST /auth/login` validates the private access token.
- `GET /auth/session` validates the current session and supports browser refresh.
- `POST /auth/logout` revokes the current session and deletes the cookie.
- All trading, settings, workflow, scanner, signal, journal, and market endpoints require a valid session.
- Session lifetime and cookie behavior are configured only through backend environment variables.

For HTTPS production deployment, use:

```env
APP_ENV=production
TRADEHAWK_SESSION_COOKIE_SECURE=true
TRADEHAWK_SESSION_COOKIE_SAMESITE=lax
```

Use `SameSite=none` only when the frontend and backend are genuinely cross-site, and keep `TRADEHAWK_SESSION_COOKIE_SECURE=true`.

## Local development

Backend:

```bash
cd backend
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Frontend:

```bash
npm install
npm run dev
```

Verification commands:

```bash
npm run lint
npm run build
```

Bybit API keys and Supabase service-role credentials remain backend-only. TradeHawk exposes Bybit Demo Trading only through `https://api-demo.bybit.com`; Testnet, paper trading, mock trading, and live trading are not enabled.

## Scanner and Signals backend wiring

- Scanner uses authenticated `POST /scan` through `src/api/client.ts` and displays all backend outcomes: actionable, rejected, skipped, and failed.
- Signals uses authenticated `GET /signals` and displays only backend-generated signals allowed by the existing risk profile.
- Scanner and Signals no longer use seeded records, random UI updates, simulated execution, or scanner/signal localStorage data.
- Existing Demo-only lock, authentication, trading logic, Dashboard, Active Trades, Journal, Chart, and Control Center behavior remain unchanged.

## Scanner and Signals backend wiring

- Scanner uses authenticated `POST /scan` through `src/api/client.ts` and displays all backend outcomes: actionable, rejected, skipped, and failed.
- Signals uses authenticated `GET /signals` and displays only backend-generated signals allowed by the existing risk profile.
- Scanner and Signals no longer use seeded records, random UI updates, simulated execution, or scanner/signal localStorage data.
- Existing Demo-only lock, authentication, trading logic, Dashboard, Active Trades, Journal, Chart, and Control Center behavior remain unchanged.

## Chart and Control Center backend wiring

- `GET /chart-context` returns real closed Bybit Demo candles; unavailable indicators remain null.
- `GET/POST /settings` is the persistent source of truth for Control Center settings.
- `POST /engine/control` performs existing backend control actions without fabricated success states.
- Scalping and Intraday risk profiles persist separately; legacy shared values are migrated into both profiles without changing execution logic.

## Performance & Strategy

The protected `GET /performance-analysis` endpoint derives analytics from the same persisted closed-trade records used by Dashboard and Operator Journal. It supports UTC date/time, mode, strategy, status, and exit-reason filters. Missing historical mode, strategy, or exit reason remains Unknown/N/A; no retrospective explanation is generated.
