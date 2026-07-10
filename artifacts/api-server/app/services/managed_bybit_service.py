from fastapi import HTTPException

from app.services.bybit_service import BybitService


class ManagedBybitService(BybitService):
    """Apply managed-order protection and explicit symbol leverage."""

    def set_symbol_leverage(self, symbol: str, leverage: int) -> None:
        if leverage <= 0:
            raise HTTPException(status_code=400, detail="Leverage must be positive.")
        payload = {
            "category": "linear",
            "symbol": symbol.upper(),
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage),
        }
        try:
            self._private_post("/v5/position/set-leverage", payload)
        except HTTPException as exc:
            detail = str(exc.detail)
            if "110043" not in detail and "not modified" not in detail.lower():
                raise

    def create_private_order(self, payload: dict) -> dict:
        order_payload = dict(payload)
        is_entry_order = not bool(order_payload.get("reduceOnly"))
        if is_entry_order and order_payload.get("stopLoss"):
            order_payload.pop("takeProfit", None)
            order_payload.pop("tpTriggerBy", None)
        return super().create_private_order(order_payload)
