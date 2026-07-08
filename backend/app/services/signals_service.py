from fastapi import HTTPException

from app.core.enums import SignalGrade, Timeframe, TradingMode
from app.schemas.signals import SignalFilters, SignalItem, SignalsData, SignalsResponse
from app.services.settings_service import SettingsService
from app.services.strategy_service import StrategyService


class SignalsService:
    def __init__(
        self,
        settings_service: SettingsService,
        strategy_service: StrategyService,
    ) -> None:
        self._settings_service = settings_service
        self._strategy_service = strategy_service

    def get_signals(
        self,
        mode: TradingMode | None,
        grade: SignalGrade | None,
        symbol: str | None,
        timeframe: Timeframe | None,
    ) -> SignalsResponse:
        selected_mode = mode or self._settings_service.get_mode_summary().data.active_strategy_mode
        normalized_symbol = symbol.strip().upper() if symbol else None
        settings_state = self._settings_service.get_settings_state()
        symbols = [normalized_symbol] if normalized_symbol else self._strategy_service.default_symbols(selected_mode)
        signals: list[SignalItem] = []

        for item_symbol in symbols:
            try:
                signal_item = self._strategy_service.evaluate_symbol(
                    symbol=item_symbol,
                    mode=selected_mode,
                    timeframe=timeframe,
                )
            except HTTPException:
                continue
            if signal_item is None:
                continue
            if signal_item.grade not in settings_state.allowed_signal_grades:
                continue
            if grade is not None and signal_item.grade != grade:
                continue

            signals.append(
                SignalItem(
                    signal_id=(
                        f"sig-{signal_item.symbol.lower()}-"
                        f"{signal_item.timeframe.value.lower()}-{signal_item.direction.value}"
                    ),
                    symbol=signal_item.symbol,
                    direction=signal_item.direction,
                    grade=signal_item.grade,
                    mode=signal_item.mode,
                    timeframe=signal_item.timeframe,
                    status=signal_item.status,
                    strategy="EMA/RSI trend evaluation",
                    reason=signal_item.reason,
                    entry_price=signal_item.entry_price,
                    current_price=signal_item.current_price,
                )
            )

        return SignalsResponse(
            message="Signals fetched successfully.",
            data=SignalsData(
                filters=SignalFilters(
                    mode=selected_mode,
                    grade=grade,
                    symbol=normalized_symbol,
                    timeframe=timeframe,
                ),
                signals=signals,
            ),
        )
