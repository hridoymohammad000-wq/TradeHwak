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

        signals: list[SignalItem] = []
        for signal_item in evaluated:
            if signal_item.status != "armed":
                continue
            if signal_item.grade not in settings_state.allowed_signal_grades:
                continue
            if timeframe is not None and signal_item.timeframe != timeframe:
                continue
            if grade is not None and signal_item.grade != grade:
                continue

            metrics = signal_item.metrics or {}
            entry = float(signal_item.entry_price)
            atr = float(metrics.get("atr14") or 0)
            swing_low = float(metrics.get("swing_low") or 0)
            swing_high = float(metrics.get("swing_high") or 0)

            if signal_item.direction.value == "buy":
                structural_stop = swing_low if 0 < swing_low < entry else entry - atr
                stop_loss = min(structural_stop, entry - max(atr * 0.8, entry * 0.0035))
                risk = entry - stop_loss
                take_profit = entry + risk * 2
            else:
                structural_stop = swing_high if swing_high > entry else entry + atr
                stop_loss = max(structural_stop, entry + max(atr * 0.8, entry * 0.0035))
                risk = stop_loss - entry
                take_profit = entry - risk * 2

            strategy = (
                "EMA Pullback Scalping"
                if signal_item.mode == TradingMode.SCALPING
                else "Trend Continuation Intraday"
            )
            higher_timeframe = "H1" if signal_item.mode == TradingMode.SCALPING else "H4"
            score = float(metrics.get("final_score") or 0)
            htf_score = float(metrics.get("higher_timeframe_score") or 0)

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
                    higher_timeframe=higher_timeframe,
                    status=signal_item.status,
                    strategy=strategy,
                    reason=signal_item.reason,
                    entry_price=round(entry, 8),
                    current_price=round(float(signal_item.current_price), 8),
                    stop_loss=round(stop_loss, 8),
                    take_profit=round(take_profit, 8),
                    risk_reward=2.0,
                    score=round(score, 2),
                    confidence=round(score, 2),
                    htf_score=round(htf_score, 2),
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
