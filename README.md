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

Completed on July 13, 2026.

Automatic trading now checks PostgreSQL readiness before it can be enabled or run. The readiness gate verifies the database connection, required execution tables, settings access, trade state access, and executed signal history access, and startup restore now fails closed if settings, persisted trade state, or executed signal IDs cannot be loaded safely.

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

### Status

Completed on July 12, 2026.

Scalping and intraday now use separate V2 trading rules for setup timeframe, risk per trade, minimum risk-to-reward, daily net loss limits, maximum trade duration, and trailing-stop behavior. The combined daily loss and open-position limits are enforced through the shared V2 rule configuration.

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

### Status

Completed on July 12, 2026.

The backend now runs independent workers for scanner/execution, trade management, and exchange reconciliation. Scanner cycles run every 5 minutes, trade management runs every 15 seconds, and exchange reconciliation runs every 30 seconds.

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

### Status

Completed on July 12, 2026.

Position sizing now calculates risk from total account equity and performs a final pre-order validation against available margin, configured leverage, total open exposure, exchange quantity and notional limits, and existing open-position risk.

---

### 6. Multi-Worker Duplicate Execution

The current cycle lock works only inside one Python process.

If multiple Render workers or instances run simultaneously, more than one process may execute the same workflow.

### Required Fix

Implement a PostgreSQL-based distributed lock or advisory lock.

The execution flow must also use a unique order-link ID for exchange-level idempotency.

### Status

Completed on July 12, 2026.

Automatic trading now uses a PostgreSQL advisory lock for distributed cycle coordination, and entry orders now include deterministic `orderLinkId` values so retries and multi-worker replays reuse the same exchange-side identity.

---

### 7. Exchange Reconciliation

The current exchange reconciliation is installed using a runtime monkey patch.

This makes the application harder to maintain and increases the risk of unexpected behaviour.

### Required Fix

Move reconciliation directly into the canonical `TradeService`.

Exchange positions and closed orders must be matched using stable exchange identifiers instead of symbol-only matching.

### Status

Completed on July 13, 2026.

Authoritative exchange reconciliation now lives directly inside the canonical `TradeService`. Open positions are treated as exchange-authoritative, closed orders are imported with stable exchange-derived identifiers, open-position reconciliation now uses identity-first matching instead of symbol-only pairing, and repeated refreshes remain idempotent without relying on a runtime monkey patch.

---

### 8. Scanner Error Visibility

Completed on July 12, 2026.

Scanner responses now expose a structured breakdown for scanned, actionable, rejected, skipped, failed, exchange-error, and insufficient-data outcomes. Non-actionable symbols are also returned with per-symbol issue details so market-data failures are no longer indistinguishable from ordinary strategy rejection.

Some market-data and strategy errors were previously silently skipped.

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

### V2 Status Checklist

- [x] V2-001 - Backend API Authentication
- [x] V2-002 - Production Database Safety
- [x] V2-003 - Trading Rule Alignment
- [x] V2-004 - Independent Trade Management Worker
- [x] V2-005 - Position Sizing and Margin Validation
- [x] V2-006 - Distributed Lock and Idempotency
- [x] V2-007 - Exchange Reconciliation Rewrite
- [x] V2-008 - Scanner Error Reporting
- [x] V2-009 - Full Regression and Runtime Tests
- [x] V2-010 - Production Readiness Review

```text
V2-001 — Backend API Authentication (Completed on July 12, 2026)
V2-002 — Production Database Safety (Completed on July 13, 2026)
V2-003 — Trading Rule Alignment (Completed on July 12, 2026)
V2-004 — Independent Trade Management Worker (Completed on July 12, 2026)
V2-005 — Position Sizing and Margin Validation (Completed on July 12, 2026)
V2-006 — Distributed Lock and Idempotency (Completed on July 12, 2026)
V2-007 — Exchange Reconciliation Rewrite (Completed on July 13, 2026)
V2-008 — Scanner Error Reporting (Completed on July 12, 2026)
V2-009 — Full Regression and Runtime Tests (Completed on July 13, 2026)
V2-010 — Production Readiness Review (Completed on July 13, 2026)
```

### V2-009 Verification Summary

Completed on July 13, 2026.

Verified with full backend regression (`190/190` tests passing), frontend validation (`npm run lint`), frontend production build (`npm run build`), and a live local backend runtime health check returning HTTP 200 from `/health`. Backend CI requirements now also include the `httpx2` dependency required by current FastAPI/Starlette `TestClient` imports.

### V2-010 Production Readiness Review Summary

Completed on July 13, 2026.

Production readiness review tightened canonical backend CORS so localhost origins are no longer auto-allowed in production, and the `/health` endpoint now reports degraded readiness with a concrete block reason when PostgreSQL persistence is not configured or not ready. Final deployment readiness still requires a real production `DATABASE_URL` to be present so health can return `persistence_ready=true`.

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

## Recent Updates

Updated on July 14, 2026.

* Scanner now shows a pipeline summary for scanned, rejected, skipped, moved-to-signals, and remaining rows.
* AI Signals now keeps both `armed` and Grade-A `watching` setups visible for review.
* Closed-trade reconciliation now deduplicates repeated exchange-close rows so Journal, Dashboard, and Performance totals stay aligned.
* Health/readiness, login hardening, and deployment portability changes are included in the current code and tests.

---

## TradeHawk V2 - Remaining Fix Checklist

### Critical

- [x] `V2-011 - Distributed Lock Repair`
  একই PostgreSQL connection পুরো auto-trade cycle পর্যন্ত ধরে রাখতে হবে। বর্তমান advisory lock connection close হলেই release হয়ে যায়।
- [x] `V2-012 - Database Fail-Closed Persistence`
  Trade, settings, journal, signal ID বা challenge save ব্যর্থ হলে exception দিতে হবে; silently ignore করা যাবে না।
- [x] `V2-013 - Startup Database Safety`
  Migration/database initialization fail হলে background workers start হবে না।
- [x] `V2-014 - Multi-Worker Coordination`
  Scanner, trade manager ও reconciliation-এর জন্য shared leader-lock/coordination যোগ করতে হবে।
- [x] `V2-015 - Exchange Reconciliation Idempotency`
  Symbol নয় - `orderId`, `execId`, `positionIdx` ও stable trade identity দিয়ে matching করতে হবে; duplicate journal/P&L বন্ধ করতে হবে।
- [x] `V2-016 - Imported Trade Mode Preservation`
  Exchange trade-কে current selected mode দিয়ে label না করে original scalping/intraday mode restore করতে হবে।
- [x] `V2-017 - SL/TP Confirmation and Emergency Close`
  Entry-এর পরে SL/TP exchange-এ সত্যিই attached হয়েছে কি না verify করতে হবে; দুইবার failure হলে reduce-only emergency close করতে হবে।
- [x] `V2-018 - Atomic TP1/TP2 Management`
  Partial exit fill confirm হওয়ার আগে `tp1_done`/`tp2_done` set করা যাবে না; retry-safe state machine করতে হবে।

### Trading Engine

- [x] `V2-019 - Rank Before Execute`
  সব symbol evaluate -> score অনুযায়ী rank -> best signals select -> তারপর order execute করতে হবে।
- [x] `V2-020 - Auto Scanner Error Reporting`
  Automatic cycle-এও `rejected`, `failed`, `exchange_error` ও `insufficient_data` আলাদা report করতে হবে।
- [x] `V2-021 - Signal Identity Redesign`
  Signal ID-তে candle timestamp/setup identity যোগ করতে হবে; একই symbol-direction-এর valid নতুন signal যেন পুরো দিন block না হয়।
- [x] `V2-022 - OrderLinkId Collision Prevention`
  Manual ও automatic orders-এর unique deterministic order identity নিশ্চিত করতে হবে।
- [x] `V2-023 - Spread and Liquidity Gate`
  Bid-ask spread বেশি হলে symbol skip করতে হবে; minimum liquidity/slippage rule যোগ করতে হবে।
- [x] `V2-024 - Fresh Price for Trade Management`
  15-second trade manager-কে stale reconciliation price নয়, fresh ticker/position price ব্যবহার করতে হবে।
- [x] `V2-025 - Single Risk Authority`
  Fixed V2 scalping/intraday rules এবং editable Control Center risk fields-এর conflict সরাতে হবে।

### Double Down Challenge

- [x] `V2-026 - Safe API Response Parsing`
  `response.json()` সরাসরি না করে empty/non-JSON response handle করতে হবে; canonical API client ব্যবহার করতে হবে।
- [x] `V2-027 - Backend Error Contract Alignment`
  Frontend `detail` নয়, backend-এর `message`/`data` envelope সঠিকভাবে parse করবে।
- [x] `V2-028 - Challenge Persistence Fail-Closed`
  Challenge DB save fail হলে success response দেওয়া যাবে না।
- [x] `V2-029 - Challenge Readiness Check`
  `double_down_challenges` table ও challenge persistence `/health` readiness check-এর অংশ করতে হবে।
- [x] `V2-030 - Complete Challenge Execution Wiring`
  Cycle planning, strategy selection, demo order execution, protection, reconciliation ও P&L close API/service-এর সঙ্গে connect করতে হবে।
- [x] `V2-031 - Multiple Challenge Management`
  Challenge list/selector এবং active challenge নির্বাচন ব্যবস্থা যোগ করতে হবে।

### Production And Verification

- [x] `V2-032 - Real Health/Readiness Endpoint`
  Database/Bybit/worker/table failure হলে HTTP `503` দিতে হবে; শুধু body-তে `degraded` যথেষ্ট নয়।
- [x] `V2-033 - CSRF and Login Hardening`
  Mutation routes-এ CSRF/origin validation, login rate limit ও failed-attempt protection যোগ করতে হবে।
- [x] `V2-034 - Deployment Portability`
  Hardcoded Render URL সরিয়ে environment-based configuration করতে হবে।
- [ ] `V2-035 - Migration Versioning`
  একক `001_init.sql` বদলে versioned migrations ও migration history যোগ করতে হবে।
- [ ] `V2-036 - Database Pooling and Log Retention`
  PostgreSQL connection pool এবং execution-log cleanup/retention policy যোগ করতে হবে।
- [ ] `V2-037 - Full Runtime Test Evidence`
  Real PostgreSQL integration, multi-worker collision, restart recovery, Bybit Demo smoke test এবং browser E2E test চালাতে হবে।
- [ ] `V2-038 - README Status Correction`
  Runtime evidence ছাড়া V2 task "Completed" লেখা যাবে না; বর্তমান checklist status evidence অনুযায়ী update করতে হবে।

### Fix Order

**প্রথমে:** `V2-011 -> V2-018`  
**তারপর:** `V2-019 -> V2-025`  
**এরপর:** `V2-026 -> V2-031`  
**শেষে:** `V2-032 -> V2-038`

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
