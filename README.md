# TradeHawk Intraday Terminal

## Project Overview

TradeHawk Intraday Terminal is a professional React + Vite frontend for the TradeHawk FastAPI backend. It is built for Bybit Demo intraday operation only. The frontend shows dashboard status, scanner results, signals, active demo trades, trade journal, performance, control center, and settings.

**Safety note:** Bybit Demo only. Real trading is not enabled. Paper Trading, Testnet Trading, and Scalping execution are not exposed in this UI.

**Backend note:** The backend lives separately in the TradeHawk backend repository under `artifacts/api-server`. This frontend connects to that backend through `VITE_API_BASE_URL` or same-origin routes.

## Install

```bash
npm install
```

## Configure Backend URL

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Set the backend API base URL:

```env
VITE_API_BASE_URL=https://your-render-backend.onrender.com
```

Leave it blank only when the frontend and backend are served from the same origin:

```env
VITE_API_BASE_URL=
```

## Authentication

The backend requires `TRADEHAWK_ACCESS_TOKEN`. The frontend login calls:

```text
POST /auth/login
GET /auth/session
POST /auth/logout
```

The backend sets an HttpOnly cookie session named `tradehawk_session`. API requests use `credentials: "include"` so the browser sends the cookie automatically.

## Run Locally

```bash
npm run dev
```

Vite runs on port `3000` by default.

## Build

```bash
npm run build
```

The production output is created in `dist/`.

## Backend Endpoint Mapping

The frontend uses the existing TradeHawk backend routes:

- `GET /health`
- `POST /auth/login`
- `GET /auth/session`
- `POST /auth/logout`
- `GET /api/dashboard-summary`
- `POST /api/scan`
- `GET /api/signals`
- `GET /api/active-trades`
- `GET /api/closed-trades`
- `GET /api/settings`
- `POST /api/settings`
- `POST /api/bot/start`
- `POST /api/bot/stop`
- `POST /api/engine/control`

If a backend endpoint is unavailable, the UI shows an empty/error state and does not invent trading or performance data.
