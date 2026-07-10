from fastapi import HTTPException

from app.services.bybit_service import BybitService


class ManagedBybitService(BybitService):
    """Apply explicit symbol leverage while preserving protected orders."""

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
        # Entry orders must preserve both stop-loss and take-profit fields.
        # If Bybit rejects the protected order, the caller receives the error
        # and no unprotected fallback order is submitted.
        return super().create_private_order(dict(payload))
