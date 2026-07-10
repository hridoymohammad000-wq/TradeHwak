from app.services.auto_trade_service import AutoTradeService
from app.services.trailing_stop_service import TrailingStopService


class ManagedAutoTradeService(AutoTradeService):
    def __init__(self, *args, trailing_stop_service: TrailingStopService, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._trailing_stop_service = trailing_stop_service

    def run_cycle(self) -> dict[str, int | str]:
        result = super().run_cycle()
        trailing = self._trailing_stop_service.manage_open_trades()
        return {**result, **{f"trailing_{key}": value for key, value in trailing.items()}}
