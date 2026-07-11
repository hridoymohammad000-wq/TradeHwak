from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException

from app.core.enums import Direction
from app.services.trade_service import ManagedTrade, TradeService


def _closed_trade_key(row: dict) -> str:
    order_id = str(row.get("orderId") or row.get("execId") or "").strip()
    symbol = str(row.get("symbol") or "UNKNOWN").upper()
    updated = str(row.get("updatedTime") or row.get("createdTime") or "unknown")
    pnl = str(row.get("closedPnl") or "0")
    return f"exchange-closed:{order_id or f'{symbol}:{updated}:{pnl}'}"


def _managed_from_closed_row(service: TradeService, row: dict, selected_mode) -> ManagedTrade:
    symbol = str(row.get("symbol") or "").upper()
    side = str(row.get("side") or "").lower()
    direction = Direction.BUY if side == "buy" else Direction.SELL
    entry = service._safe_float(row.get("avgEntryPrice") or row.get("entryPrice"), 0.0)
    exit_price = service._safe_float(row.get("avgExitPrice") or row.get("fillPrice"), entry)
    qty = str(row.get("qty") or row.get("closedSize") or "") or None
    qty_float = service._safe_float(qty, 0.0)
    opened_at = service._to_iso_time(row.get("createdTime"))
    return ManagedTrade(
        symbol=symbol,
        mode=selected_mode,
        direction=direction,
        entry_price=entry,
        current_price=exit_price,
        stop_loss=0.0,
        take_profit=0.0,
        pnl=service._safe_float(row.get("closedPnl"), 0.0),
        timeframe=None,
        status="exchange_closed_imported",
        qty=qty,
        notional=qty_float * entry if qty_float > 0 and entry > 0 else None,
        planned_risk_usdt=None,
        risk_reward=None,
        order_id=_closed_trade_key(row),
        opened_at=opened_at,
        synced_with_exchange=True,
    )


def _persist_closed(service: TradeService, trade_key: str, closed_record) -> None:
    if not service._closed_record_exists(closed_record):
        service._closed_trades.insert(0, closed_record)
    if service._repository is None:
        return
    payload = closed_record.model_dump(mode="json")
    service._repository.upsert_trade(trade_key, "closed", payload)
    service._repository.save_journal_entry(trade_key, payload)


def _authoritative_sync_with_exchange(self: TradeService, bybit_service) -> None:
    self._ensure_current_day()
    try:
        positions = bybit_service.get_open_positions()
        closed_pnls = bybit_service.get_closed_pnls(limit=100)
    except HTTPException:
        return

    positions_by_symbol = {
        str(item.get("symbol") or "").upper(): item
        for item in positions
        if self._position_is_open(item)
    }
    closed_by_symbol: dict[str, list[dict]] = defaultdict(list)
    for item in closed_pnls:
        symbol = str(item.get("symbol") or "").upper()
        if symbol:
            closed_by_symbol[symbol].append(item)
    for rows in closed_by_symbol.values():
        rows.sort(
            key=lambda row: int(str(row.get("updatedTime") or row.get("createdTime") or 0)),
            reverse=True,
        )

    selected_mode = self._settings_service.get_settings_state().active_strategy_mode
    remaining_active: list[ManagedTrade] = []
    tracked_symbols: set[str] = set()
    consumed_closed_keys: set[str] = set()

    for trade in self._active_trades:
        symbol = trade.symbol.upper()
        position = positions_by_symbol.get(symbol)
        if position:
            self._apply_position_snapshot(trade, position)
            remaining_active.append(trade)
            tracked_symbols.add(symbol)
            self._persist_active_trade(trade)
            continue

        candidates = closed_by_symbol.get(symbol, [])
        closed_row = next(
            (row for row in candidates if _closed_trade_key(row) not in consumed_closed_keys),
            None,
        )
        if closed_row is not None:
            consumed_closed_keys.add(_closed_trade_key(closed_row))
            closed_record = self._to_closed_record(trade, closed_row)
            _persist_closed(self, self._trade_key(trade), closed_record)
            continue

        # Exchange open positions are authoritative. A locally active trade that is
        # absent from the exchange must not remain visible as an open position.
        # Keep no active record; a later closed-PnL page can still import it by its
        # unique exchange close key.

    for symbol, position in positions_by_symbol.items():
        if symbol in tracked_symbols:
            continue
        imported = self._from_exchange_position(position, selected_mode)
        remaining_active.append(imported)
        self._persist_active_trade(imported)

    # Import every exchange close, including manual and previously untracked trades.
    # A unique exchange key prevents refreshes from creating duplicates, while the
    # list-based grouping preserves multiple closes for the same symbol.
    for row in closed_pnls:
        key = _closed_trade_key(row)
        if key in consumed_closed_keys:
            continue
        managed = _managed_from_closed_row(self, row, selected_mode)
        closed_record = self._to_closed_record(managed, row)
        _persist_closed(self, key, closed_record)

    self._active_trades = remaining_active
    self._recalculate_daily_trade_count()


def install_exchange_reconciliation_patch() -> None:
    TradeService.sync_with_exchange = _authoritative_sync_with_exchange
