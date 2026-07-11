from app.services.auto_trade_service import AutoTradeService
from app.services.trade_management_service import TradeManagementService


class ManagedAutoTradeService(AutoTradeService):
    def __init__(
        self,
        *args,
        trade_management_service: TradeManagementService,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._trade_management_service = trade_management_service

    def _run_cycle(self) -> dict[str, int | str]:
        result = super()._run_cycle()
        management = self._trade_management_service.manage_open_trades()
        return {
            **result,
            **{f"management_{key}": value for key, value in management.items()},
        }
