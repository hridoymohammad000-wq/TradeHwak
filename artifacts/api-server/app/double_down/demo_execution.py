from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from app.double_down.enums import ChallengeDirection, ChallengeExchangeMode
from app.double_down.risk import PositionSizeResult


class DemoOrderStatus(StrEnum):
    CREATED = "created"
    FILLED = "filled"
    PROTECTED = "protected"
    EMERGENCY_CLOSED = "emergency_closed"
    REJECTED = "rejected"


@dataclass(frozen=True)
class DemoExecutionIntent:
    challenge_id: str
    cycle_number: int
    slot_key: str
    symbol: str
    direction: ChallengeDirection
    size: PositionSizeResult
    exchange_mode: ChallengeExchangeMode = ChallengeExchangeMode.DEMO

    @property
    def client_order_id(self) -> str:
        challenge = self.challenge_id.replace("-", "")[:12]
        slot = self.slot_key.lower().replace("_", "-")[:12]
        return f"dd-{challenge}-c{self.cycle_number}-{slot}"


@dataclass(frozen=True)
class DemoOrderReceipt:
    approved: bool
    status: DemoOrderStatus
    client_order_id: str
    exchange_order_id: str | None
    symbol: str
    quantity: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    protection_confirmed: bool
    emergency_close_order_id: str | None
    attempts: int
    rejection_code: str | None
    evidence: dict[str, str]


class DemoExchangeTransport(Protocol):
    def place_market_order(self, payload: dict[str, str]) -> dict: ...

    def attach_protection(self, payload: dict[str, str]) -> dict: ...

    def get_order(self, *, symbol: str, client_order_id: str) -> dict | None: ...

    def get_position(self, *, symbol: str) -> dict | None: ...

    def emergency_close(self, payload: dict[str, str]) -> dict: ...


class DemoChallengeExecutor:
    def __init__(self, transport: DemoExchangeTransport, *, live_trading_enabled: bool = False):
        if live_trading_enabled:
            raise ValueError("Double Down V1 live trading is prohibited")
        self._transport = transport

    def execute(self, intent: DemoExecutionIntent) -> DemoOrderReceipt:
        if intent.exchange_mode not in {ChallengeExchangeMode.DEMO, ChallengeExchangeMode.PAPER}:
            return self._reject(intent, "LIVE_MODE_BLOCKED")
        if not intent.size.approved:
            return self._reject(intent, "POSITION_SIZE_NOT_APPROVED")
        if intent.cycle_number < 1:
            return self._reject(intent, "INVALID_CYCLE_NUMBER")

        existing = self._transport.get_order(
            symbol=intent.symbol,
            client_order_id=intent.client_order_id,
        )
        if existing:
            return self._receipt_from_existing(intent, existing)

        side = "Buy" if intent.direction == ChallengeDirection.LONG else "Sell"
        entry_payload = {
            "mode": intent.exchange_mode.value,
            "symbol": intent.symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(intent.size.quantity),
            "clientOrderId": intent.client_order_id,
            "reduceOnly": "false",
        }
        entry = self._transport.place_market_order(entry_payload)
        if not self._accepted(entry):
            return self._reject(
                intent,
                "ENTRY_REJECTED",
                evidence={"exchange_message": str(entry.get("message") or "unknown")},
            )

        exchange_order_id = str(entry.get("order_id") or "") or None
        protection_attempts = 0
        protection = None
        for _ in range(2):
            protection_attempts += 1
            protection = self._transport.attach_protection(
                {
                    "mode": intent.exchange_mode.value,
                    "symbol": intent.symbol,
                    "stopLoss": str(intent.size.stop_loss),
                    "takeProfit": str(intent.size.take_profit),
                    "clientOrderId": f"{intent.client_order_id}-protect",
                }
            )
            if self._accepted(protection) and bool(protection.get("confirmed")):
                return DemoOrderReceipt(
                    approved=True,
                    status=DemoOrderStatus.PROTECTED,
                    client_order_id=intent.client_order_id,
                    exchange_order_id=exchange_order_id,
                    symbol=intent.symbol,
                    quantity=intent.size.quantity,
                    entry_price=intent.size.entry_price,
                    stop_loss=intent.size.stop_loss,
                    take_profit=intent.size.take_profit,
                    protection_confirmed=True,
                    emergency_close_order_id=None,
                    attempts=protection_attempts,
                    rejection_code=None,
                    evidence={"mode": intent.exchange_mode.value, "protection": "confirmed"},
                )

        close = self._transport.emergency_close(
            {
                "mode": intent.exchange_mode.value,
                "symbol": intent.symbol,
                "side": "Sell" if side == "Buy" else "Buy",
                "qty": str(intent.size.quantity),
                "reduceOnly": "true",
                "clientOrderId": f"{intent.client_order_id}-emergency",
            }
        )
        close_id = str(close.get("order_id") or "") or None
        return DemoOrderReceipt(
            approved=False,
            status=DemoOrderStatus.EMERGENCY_CLOSED,
            client_order_id=intent.client_order_id,
            exchange_order_id=exchange_order_id,
            symbol=intent.symbol,
            quantity=intent.size.quantity,
            entry_price=intent.size.entry_price,
            stop_loss=intent.size.stop_loss,
            take_profit=intent.size.take_profit,
            protection_confirmed=False,
            emergency_close_order_id=close_id,
            attempts=protection_attempts,
            rejection_code="PROTECTION_FAILED_EMERGENCY_CLOSE",
            evidence={
                "mode": intent.exchange_mode.value,
                "protection_message": str((protection or {}).get("message") or "unknown"),
                "emergency_close_accepted": str(self._accepted(close)).lower(),
            },
        )

    def reconcile(self, intent: DemoExecutionIntent) -> DemoOrderReceipt:
        order = self._transport.get_order(
            symbol=intent.symbol,
            client_order_id=intent.client_order_id,
        )
        position = self._transport.get_position(symbol=intent.symbol)
        if not order and not position:
            return self._reject(intent, "ORDER_AND_POSITION_NOT_FOUND")
        if position and not bool(position.get("protected")):
            close = self._transport.emergency_close(
                {
                    "mode": intent.exchange_mode.value,
                    "symbol": intent.symbol,
                    "side": "Sell" if intent.direction == ChallengeDirection.LONG else "Buy",
                    "qty": str(intent.size.quantity),
                    "reduceOnly": "true",
                    "clientOrderId": f"{intent.client_order_id}-reconcile-close",
                }
            )
            return DemoOrderReceipt(
                approved=False,
                status=DemoOrderStatus.EMERGENCY_CLOSED,
                client_order_id=intent.client_order_id,
                exchange_order_id=str((order or {}).get("order_id") or "") or None,
                symbol=intent.symbol,
                quantity=intent.size.quantity,
                entry_price=intent.size.entry_price,
                stop_loss=intent.size.stop_loss,
                take_profit=intent.size.take_profit,
                protection_confirmed=False,
                emergency_close_order_id=str(close.get("order_id") or "") or None,
                attempts=1,
                rejection_code="UNPROTECTED_POSITION_RECONCILED",
                evidence={"emergency_close_accepted": str(self._accepted(close)).lower()},
            )
        return self._receipt_from_existing(intent, order or position or {})

    @staticmethod
    def _accepted(payload: dict | None) -> bool:
        return bool(payload) and bool(payload.get("accepted"))

    def _receipt_from_existing(self, intent: DemoExecutionIntent, payload: dict) -> DemoOrderReceipt:
        protected = bool(payload.get("protected"))
        return DemoOrderReceipt(
            approved=protected,
            status=DemoOrderStatus.PROTECTED if protected else DemoOrderStatus.FILLED,
            client_order_id=intent.client_order_id,
            exchange_order_id=str(payload.get("order_id") or "") or None,
            symbol=intent.symbol,
            quantity=intent.size.quantity,
            entry_price=intent.size.entry_price,
            stop_loss=intent.size.stop_loss,
            take_profit=intent.size.take_profit,
            protection_confirmed=protected,
            emergency_close_order_id=None,
            attempts=0,
            rejection_code=None if protected else "EXISTING_ORDER_NOT_PROTECTED",
            evidence={"idempotent_reuse": "true"},
        )

    def _reject(
        self,
        intent: DemoExecutionIntent,
        code: str,
        *,
        evidence: dict[str, str] | None = None,
    ) -> DemoOrderReceipt:
        return DemoOrderReceipt(
            approved=False,
            status=DemoOrderStatus.REJECTED,
            client_order_id=intent.client_order_id,
            exchange_order_id=None,
            symbol=intent.symbol,
            quantity=intent.size.quantity,
            entry_price=intent.size.entry_price,
            stop_loss=intent.size.stop_loss,
            take_profit=intent.size.take_profit,
            protection_confirmed=False,
            emergency_close_order_id=None,
            attempts=0,
            rejection_code=code,
            evidence=evidence or {},
        )
