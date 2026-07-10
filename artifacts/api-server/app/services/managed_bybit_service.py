from app.services.bybit_service import BybitService


class ManagedBybitService(BybitService):
    """Ensure managed trades keep only the protective stop on entry.

    Partial profit-taking is owned by TradeManagementService, so a full-position
    exchange take-profit must not close the position before staged exits run.
    """

    def create_private_order(self, payload: dict) -> dict:
        order_payload = dict(payload)
        is_entry_order = not bool(order_payload.get("reduceOnly"))
        if is_entry_order and order_payload.get("stopLoss"):
            order_payload.pop("takeProfit", None)
            order_payload.pop("tpTriggerBy", None)
        return super().create_private_order(order_payload)
