from threading import Lock

from fastapi import HTTPException, status

from app.schemas.scanner import ScanData, ScanRequest, ScanResponse, ScanResult
from app.services.settings_service import SettingsService
from app.services.signal_registry import SignalRegistry
from app.services.strategy_service import StrategyService, StrategySignal


class ScannerService:
    MAX_RESULTS = 10

    def __init__(
        self,
        settings_service: SettingsService,
        strategy_service: StrategyService,
        signal_registry: SignalRegistry,
    ) -> None:
        self._settings_service = settings_service
        self._strategy_service = strategy_service
        self._signal_registry = signal_registry
        self._scan_lock = Lock()

    @staticmethod
    def _score(signal: StrategySignal) -> float:
        try:
            return float(signal.metrics.get("final_score", 0.0))
        except (AttributeError, TypeError, ValueError):
            return 0.0

    def scan(self, payload: ScanRequest | None) -> ScanResponse:
        if not self._scan_lock.acquire(blocking=False):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A scan is already running. Wait for it to finish before starting another scan.",
            )

        try:
            request = payload or ScanRequest()
            selected_mode = (
                request.mode
                or self._settings_service.get_mode_summary().data.active_strategy_mode
            )
            symbols = request.symbols or self._strategy_service.default_symbols(selected_mode)
            evaluated_signals: list[StrategySignal] = []

            for symbol in symbols:
                try:
                    signal = self._strategy_service.evaluate_symbol(
                        symbol=symbol,
                        mode=selected_mode,
                        timeframe=request.timeframe,
                    )
                except HTTPException:
                    continue
                if signal is not None:
                    evaluated_signals.append(signal)

            ranked = sorted(
                evaluated_signals,
                key=lambda signal: (self._score(signal), signal.symbol),
                reverse=True,
            )
            filtered = [
                signal
                for signal in ranked
                if (request.direction is None or signal.direction == request.direction)
                and (request.grade is None or signal.grade == request.grade)
            ][: self.MAX_RESULTS]

            self._signal_registry.replace(
                selected_mode,
                evaluated_signals,
                source="manual_scan",
            )
            return ScanResponse(
                message="Scan completed.",
                data=ScanData(
                    mode=selected_mode,
                    timeframe=request.timeframe
                    or self._strategy_service.default_timeframe(selected_mode),
                    results=[
                        ScanResult(
                            symbol=signal.symbol,
                            mode=signal.mode,
                            timeframe=signal.timeframe,
                            direction=signal.direction,
                            grade=signal.grade,
                            reason=signal.reason,
                        )
                        for signal in filtered
                    ],
                ),
            )
        finally:
            self._scan_lock.release()
