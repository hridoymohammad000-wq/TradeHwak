# TradeHawk Crypto Bot

TradeHawk is a web-based cryptocurrency trading workspace built for automated **Bybit Demo Trading**.

The application combines market scanning, strategy analysis, risk management, demo order execution, trade monitoring, journaling, and performance review inside one dashboard.

> **Important:** TradeHawk currently supports demo trading only. Live trading is not enabled.

---

## Main Features

* Bybit Demo API integration
* Automatic market scanning
* Scalping and intraday strategy modes
* A+ and A-grade signal filtering
* Automated demo trade execution
* Stop-loss and take-profit protection
* Daily loss and trade limits
* Maximum open-position control
* Duplicate signal protection
* Active-trade monitoring
* Trade journal and performance analysis
* Double Down Challenge workspace
* PostgreSQL persistence
* React dashboard with FastAPI backend
* One-click bot start and stop controls

---

## Technology Stack

### Frontend

* React
* TypeScript
* Vite
* Tailwind CSS
* Lightweight Charts

### Backend

* Python
* FastAPI
* Pydantic
* PostgreSQL
* Bybit V5 Demo API

### Deployment

* Render
* Single-service frontend and backend deployment

---

## Repository Structure

```text
/
├── artifacts/api-server/   # Canonical FastAPI backend
├── backend/                # Legacy backend, not used in production
├── src/                    # React frontend
├── dist/                   # Production frontend build
├── render.yaml             # Render deployment configuration
└── README.md
```

The canonical production backend is:

```text
artifacts/api-server/
```

New backend changes must not be implemented inside the legacy `backend/` directory.

---

## Current Trading Workflow

```text
Market Scan
    ↓
Strategy Evaluation
    ↓
Signal Grading
    ↓
Risk Validation
    ↓
Bybit Demo Order
    ↓
Trade Monitoring
    ↓
Journal and Performance Review
```

The bot currently supports:

* Scalping mode
* Intraday mode
* Top-volume USDT perpetual symbols
* Breakout strategy
* Pure SMC strategy
* Hybrid liquidity-sweep strategy
* RSI and VWAP confirmation
* A+ and A-grade signals only

---

## Current Project Status

The application foundation, dashboard, demo exchange connection, scanner, signal engine, risk controls, execution workflow, trade journal, performance page, and Double Down Challenge modules have been implemented.

The latest automated checks include:

* Backend tests
* Frontend TypeScript validation
* Frontend production build
* Exchange reconciliation tests
* Production release checks

However, the application is **not yet considered V2 production-ready** because several security, persistence, and trading-rule issues were identified during the latest repository audit.

---

# TradeHawk V2

TradeHawk V2 will focus on making the current application safer, more reliable, easier to maintain, and fully aligned with the approved trading rules.

## V2 Name Options

Possible names for the next version:

1. **TradeHawk V2**
2. **TradeHawk Pro V2**
3. **TradeHawk Next**
4. **TradeHawk Edge**
5. **TradeHawk Autonomous**
6. **TradeHawk Demo Engine V2**

Recommended name:

```text
TradeHawk V2
```

This name keeps the existing product identity and clearly separates the rebuilt architecture from the current version.

---

## Newly Identified Problems

The latest audit identified several issues that must be corrected before TradeHawk V2 is considered complete.

### 1. Backend API Authentication

The frontend currently checks whether the user is logged in, but sensitive backend routes are not fully protected by server-side authentication.

Potentially affected operations include:

* Settings changes
* Starting or stopping the bot
* Manual demo trade submission
* Engine control
* Account and trade information

### Required Fix

Add a mandatory authenticated-session dependency to all private operational API routes.

Only these endpoints should remain public:

* Health check
* Login
* Logout
* Session validation

### Status

Completed on July 12, 2026.

Private operational `/api` routes now require an authenticated session, while health and authentication endpoints remain public.

---

### 2. Database Failure Safety

The backend can continue using in-memory state when PostgreSQL is unavailable.

This creates risks such as:

* Settings being lost after restart
* Daily trade count being lost
* Executed signal history being lost
* Duplicate execution after restart
* Loss-management state being reset

### Required Fix

Production execution must fail closed when PostgreSQL is unavailable.

The bot must not start automatic trading unless:

* Database connection is healthy
* Required tables are available
* Settings can be loaded
* Trade state can be restored
* Executed signal IDs can be restored

### Status

Completed on July 12, 2026.

Automatic trading now checks PostgreSQL readiness before it can be enabled or run. The readiness gate verifies the database connection, required execution tables, settings access, trade state access, and executed signal history access.

---

### 3. Trading Rule Mismatch

The current implementation does not fully match the approved trading rules.

Approved V2 rules:

#### Scalping

* Setup timeframe: 1 minute
* Risk per trade: 0.5%
* Minimum risk-to-reward: 1:1.5
* Daily maximum net loss: 2%
* Maximum trade duration: 59 minutes
* No trailing stop

#### Intraday

* Setup timeframe: 5 minutes
* Risk per trade: 1%
* Minimum risk-to-reward: 1:2
* Daily maximum net loss: 3%
* Maximum trade duration: 6 hours
* Separate intraday trade management

#### Combined

* Total daily maximum loss: 5%
* Maximum open trades: 5
* Bot stops when the combined daily loss limit is reached

### Required Fix

Separate scalping and intraday configuration instead of using one shared risk and trade-management configuration.

---

### 4. Trade Management Frequency

The current automatic workflow runs approximately every five minutes.

This is too slow for managing one-minute scalping trades because:

* Stop adjustments may be delayed
* Partial exits may be delayed
* Fast price reversals may occur before the next cycle

### Required Fix

Separate the scanner from the trade-management worker.

Recommended workflow:

```text
Scanner Worker:
Runs every 5 minutes

Trade Management Worker:
Runs every 10–15 seconds

Exchange Reconciliation:
Runs every 15–30 seconds
```

---

### 5. Position Sizing

The current position-sizing logic mainly uses available balance.

The approved model requires risk to be calculated from total account capital while also respecting:

* Available margin
* Maximum allowed exposure
* Exchange quantity limits
* Minimum notional
* Leverage
* Existing open-position risk

### Required Fix

Add a final margin-affordability and exposure check before submitting any order.

---

### 6. Multi-Worker Duplicate Execution

The current cycle lock works only inside one Python process.

If multiple Render workers or instances run simultaneously, more than one process may execute the same workflow.

### Required Fix

Implement a PostgreSQL-based distributed lock or advisory lock.

The execution flow must also use a unique order-link ID for exchange-level idempotency.

---

### 7. Exchange Reconciliation

The current exchange reconciliation is installed using a runtime monkey patch.

This makes the application harder to maintain and increases the risk of unexpected behaviour.

### Required Fix

Move reconciliation directly into the canonical `TradeService`.

Exchange positions and closed orders must be matched using stable exchange identifiers instead of symbol-only matching.

---

### 8. Scanner Error Visibility

Some market-data and strategy errors are silently skipped.

This can make these two situations look identical:

```text
No valid signal found
```

and

```text
Market data request failed
```

### Required Fix

Every scan must report separate counts for:

* Scanned
* Actionable
* Rejected
* Skipped
* Failed
* Exchange error
* Insufficient data

---

## V2 Development Order

TradeHawk V2 should be developed sequentially.

```text
V2-001 — Backend API Authentication (Completed on July 12, 2026)
V2-002 — Production Database Safety (Completed on July 12, 2026)
V2-003 — Trading Rule Alignment
V2-004 — Independent Trade Management Worker
V2-005 — Position Sizing and Margin Validation
V2-006 — Distributed Lock and Idempotency
V2-007 — Exchange Reconciliation Rewrite
V2-008 — Scanner Error Reporting
V2-009 — Full Regression and Runtime Tests
V2-010 — Production Readiness Review
```

Each task must be completed with:

* Implementation
* Automated tests
* Diff review
* Runtime verification
* Documentation update

before starting the next task.

---

## V2 Completion Conditions

TradeHawk V2 will be considered complete only when:

* All sensitive backend routes require authentication
* Database failure disables execution
* Trading rules exactly match the approved configuration
* Scalping and intraday management are separated
* Duplicate execution is prevented across workers
* Exchange positions are authoritative
* Trade-management timing is suitable for scalping
* All backend tests pass
* Frontend validation and production build pass
* Render deployment passes health and readiness checks
* Bybit Demo execution is tested safely
* No live-trading credentials or routes are enabled

---

## Security

Never commit these values to the repository:

```text
TRADEHAWK_ACCESS_TOKEN
DATABASE_URL
BYBIT_DEMO_API_KEY
BYBIT_DEMO_API_SECRET
```

Store all sensitive values using Render environment variables or another secure secret-management system.

---

## Local Development

### Backend

```bash
cd artifacts/api-server
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

### Backend Tests

```bash
cd artifacts/api-server
python -m unittest discover -s tests
```

### Frontend

```bash
npm install
npm run dev
```

### Frontend Validation

```bash
npm run lint
npm run build
```

---

## Disclaimer

TradeHawk is an experimental demo-trading application.

It does not guarantee profits, prevent losses, or provide financial advice. Strategy results, backtests, demo performance, and historical performance do not guarantee future results.

Use the application only for testing, research, education, and controlled demo-trading purposes.
