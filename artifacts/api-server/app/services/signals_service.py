from fastapi import HTTPException

from app.core.enums import SignalGrade, Timeframe, TradingMode
from app.schemas.signals import SignalFilters, SignalItem, SignalsData, SignalsResponse
from app.services.settings_service import SettingsService
from app.services.signal_registry import SignalRegistry
from app.services.strategy_service import StrategyService


class SignalsService:
    def __init__(
        self,
        settings_service: SettingsService,
        strategy_service: StrategyService,
        signal_registry: SignalRegistry,
    ) -> None:
        self._settings_service = settings_service
        self._strategy_service = strategy_service
        self._signal_registry = signal_registry

    def get_signals(
        self,
        mode: TradingMode | None,
        grade: SignalGrade | None,
        symbol: str | None,
        timeframe: Timeframe | None,
    ) -> SignalsResponse:
        selected_mode = (
            mode
            or self._settings_service.get_mode_summary().data.active_strategy_mode
        )
        normalized_symbol = symbol.strip().upper() if symbol else None
        settings_state = self._settings_service.get_settings_state()

        evaluated = self._signal_registry.get(selected_mode)
        if normalized_symbol:
            evaluated = [item for item in evaluated if item.symbol == normalized_symbol]

        if not evaluated:
            symbols = (
                [normalized_symbol]
                if normalized_symbol
                else self._strategy_service.default_symbols(selected_mode)
            )
            fresh = []
            for item_symbol in symbols:
                try:
                    signal_item = self._strategy_service.evaluate_symbol(
                        symbol=item_symbol,
                        mode=selected_mode,
                        timeframe=timeframe,
                    )
                except HTTPException:
                    continue
                if signal_item is not None:
                    fresh.append(signal_item)
            evaluated = fresh
            self._signal_registry.replace(
                selected_mode,
                fresh,
                source="signals_refresh",
            )

        filtered_signals: list[SignalItem] = []
        fallback_signals: list[SignalItem] = []
        for signal_item in evaluated:
            if timeframe is not None and signal_item.timeframe != timeframe:
                continue
            base_signal = SignalItem(
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
                entry_price=signal_item.entry_price,
                current_price=signal_item.current_price,
            )
            fallback_signals.append(base_signal)
            if signal_item.grade not in settings_state.allowed_signal_grades:
                continue
            if grade is not None and signal_item.grade != grade:
                continue
            filtered_signals.append(base_signal)

        if not filtered_signals and grade is None:
            filtered_signals = [
                signal.model_copy(update={"status": "filtered_by_risk_profile"})
                for signal in fallback_signals
            ]

        return SignalsResponse(
            message="Signals fetched successfully.",
            data=SignalsData(
                filters=SignalFilters(
                    mode=selected_mode,
                    grade=grade,
                    symbol=normalized_symbol,
                    timeframe=timeframe,
                ),
                signals=filtered_signals,
            ),
        )
