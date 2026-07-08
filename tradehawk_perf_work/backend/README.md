# TradeHawk Backend

Canonical FastAPI backend for TradeHawk. It preserves the Bybit Demo scanner, signal, strategy, risk, execution, workflow, and persistence behavior while providing private single-token authentication and one canonical trade/journal data contract.

## Required environment

Copy `.env.example` to `.env` and configure:

```env
TRADEHAWK_ACCESS_TOKEN=<unique-random-token-at-least-32-characters>
BYBIT_ENV=demo
BYBIT_BASE_URL=https://api-demo.bybit.com
```

No default access token or development bypass exists. Startup fails clearly when the token is missing or too short, without printing its value. The runtime mode list exposes Demo only.

## Session configuration

```env
TRADEHAWK_SESSION_TTL_MINUTES=480
TRADEHAWK_SESSION_COOKIE_NAME=tradehawk_session
TRADEHAWK_SESSION_COOKIE_SECURE=false
TRADEHAWK_SESSION_COOKIE_SAMESITE=lax
```

Production HTTPS deployments should set `APP_ENV=production` and `TRADEHAWK_SESSION_COOKIE_SECURE=true`.

Sessions use random opaque identifiers in an `HttpOnly` cookie. Only a SHA-256 digest of each session identifier is retained in backend memory. Logout revokes the session, and expired sessions are rejected and removed.

## Public endpoints

- `GET /health`
- `POST /auth/login`
- `POST /auth/logout`

`GET /auth/session` returns `401 Unauthorized` unless a valid session cookie is present.

## Protected existing endpoints

- `GET /mode`
- `GET /bybit/config-status`
- `GET /bybit/connection`
- `POST /bybit/test-connection`
- `GET /market/test`
- `GET /market/snapshot`
- `GET /dashboard-summary`
- `GET /settings`
- `GET /settings/view`
- `POST /settings`
- `POST /scan`
- `GET /signals`
- `GET /active-trades`
- `GET /closed-trades`
- `POST /trade/manual`
- `GET /chart-context`
- `POST /engine/control`
- `GET /workflow/status`
- `POST /workflow/run`

`/dashboard-summary`, `/active-trades`, and `/closed-trades` accept optional ISO-8601 `start_time` and `end_time` query parameters. They use the same persisted trade identifiers, normalized UTC timestamps, statuses, mode values, and PnL fields.

New trade records persist an explicit `scalping` or `intraday` mode. Legacy records without a mode remain visible with a null API value, rendered by the frontend as `Unknown`; the backend does not guess from strategy or timeframe. Journal summaries are generated server-side for Scalping, Intraday, Unknown, and Combined records.

## Run locally

```bash
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```
