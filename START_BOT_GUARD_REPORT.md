# Start Bot Load Guard

## Cause
Rapid clicks could enter `startBot()` multiple times before React committed the `commandBusy` state update. Each invocation started its own engine-control, scan, signal, and dashboard refresh request chain.

## Fix
- Added an immediate `useRef` command mutex shared by Start, Stop, and Refresh.
- Start is rejected synchronously while another command is active.
- Existing disabled-button behavior remains.
- Added a non-blocking backend scanner lock. A concurrent second scan returns HTTP 409 instead of starting duplicate scanner work.

## Logic unchanged
No strategy, scanner evaluation, signal, risk, execution, persistence, or Command Center sequence was changed.

## Files changed
- `artifacts/crypto-dashboard/src/components/pages/DashboardPage.tsx`
- `artifacts/api-server/app/services/scanner_service.py`
- `START_BOT_GUARD_REPORT.md`
