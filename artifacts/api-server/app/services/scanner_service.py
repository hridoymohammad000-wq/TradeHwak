from threading import Lock

from fastapi import HTTPException, status

from app.schemas.scanner import ScanData, ScanRequest, ScanResponse, ScanResult
from app.services.settings_service import SettingsService
from app.services.signal_registry import SignalRegistry
from app.services.strategy_service import StrategyService


class ScannerService:
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
            evaluated_signals = []
            filtered_results: list[ScanResult] = []

            for symbol in symbols:
                try:
                    signal = self._strategy_service.evaluate_symbol(
                        symbol=symbol,
                        mode=selected_mode,
                        timeframe=request.timeframe,
                    )
                except HTTPException:
                    continue
                if signal is None:
                    continue

                evaluated_signals.append(signal)
                if request.direction is not None and signal.direction != request.direction:
                    continue
                if request.grade is not None and signal.grade != request.grade:
                    continue
                filtered_results.append(
                    ScanResult(
                        symbol=signal.symbol,
                        mode=signal.mode,
                        timeframe=signal.timeframe,
                        direction=signal.direction,
                        grade=signal.grade,
                        reason=signal.reason,
                    )
                )

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
                    results=filtered_results,
                ),
            )
        finally:
            self._scan_lock.release()
