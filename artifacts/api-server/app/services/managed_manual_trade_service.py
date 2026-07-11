from fastapi import HTTPException

from app.core.enums import TradingMode
from app.schemas.trades import ManualTradeRequest, ManualTradeResponse
from app.services.manual_trade_service import ManualTradeService


class ManagedManualTradeService(ManualTradeService):
    """Enforce final execution gates immediately before order submission."""

    MODE_OPEN_LIMITS = {
        TradingMode.SCALPING: 5,
        TradingMode.INTRADAY: 3,
    }
    def execute_manual_trade(
        self,
        payload: ManualTradeRequest,
        signal_id: str | None = None,
    ) -> ManualTradeResponse:
        self._trade_service.sync_with_exchange(self._bybit_service)

        if signal_id and self._trade_service.was_signal_executed(signal_id):
            raise HTTPException(
                status_code=409,
                detail="This signal has already been executed today.",
            )

        if self._trade_service.has_open_trade_for_symbol(payload.symbol):
            raise HTTPException(
                status_code=409,
                detail=f"{payload.symbol.upper()} already has an open position.",
            )

        settings = self._settings_service.get_settings_state()
        if self._trade_service.get_daily_trade_count() >= settings.daily_max_trades:
            raise HTTPException(
                status_code=409,
                detail=f"Daily trade limit of {settings.daily_max_trades} reached.",
            )

        active = self._trade_service.get_active_trades().data
        mode_count = (
            len(active.scalping_trades)
            if payload.mode == TradingMode.SCALPING
            else len(active.intraday_trades)
        )
        mode_limit = self.MODE_OPEN_LIMITS[payload.mode]
        if mode_count >= mode_limit:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{payload.mode.value.title()} open-position limit "
                    f"of {mode_limit} reached."
                ),
            )

        overall_limit = settings.max_open_positions
        if len(active.scalping_trades) + len(active.intraday_trades) >= overall_limit:
            raise HTTPException(
                status_code=409,
                detail=f"Overall open-position limit of {overall_limit} reached.",
            )

        return super().execute_manual_trade(payload, signal_id=signal_id)
