from fastapi import HTTPException

from app.schemas.scanner import (
    ScanCounts,
    ScanData,
    ScanMetrics,
    ScanRequest,
    ScanResponse,
    ScanResult,
)
from app.services.settings_service import SettingsService
from app.services.strategy_service import StrategyService


class ScannerService:
    def __init__(
        self,
        settings_service: SettingsService,
        strategy_service: StrategyService,
    ) -> None:
        self._settings_service = settings_service
        self._strategy_service = strategy_service

    def scan(self, payload: ScanRequest | None) -> ScanResponse:
        request = payload or ScanRequest()
        selected_mode = request.mode or self._settings_service.get_mode_summary().data.active_strategy_mode
        selected_timeframe = request.timeframe or self._strategy_service.default_timeframe(selected_mode)
        symbols = request.symbols or self._strategy_service.default_symbols(selected_mode)
        results: list[ScanResult] = []

        for symbol in symbols:
            try:
                signal = self._strategy_service.evaluate_symbol(
                    symbol=symbol,
                    mode=selected_mode,
                    timeframe=request.timeframe,
                )
            except HTTPException as exc:
                results.append(
                    ScanResult(
                        symbol=symbol,
                        outcome="failed",
                        mode=selected_mode,
                        timeframe=selected_timeframe,
                        failure_reason=str(exc.detail),
                    )
                )
                continue
            except Exception as exc:
                results.append(
                    ScanResult(
                        symbol=symbol,
                        outcome="failed",
                        mode=selected_mode,
                        timeframe=selected_timeframe,
                        failure_reason=type(exc).__name__,
                    )
                )
                continue

            if signal is None:
                results.append(
                    ScanResult(
                        symbol=symbol,
                        outcome="rejected",
                        mode=selected_mode,
                        timeframe=selected_timeframe,
                        rejection_reason="No strategy setup satisfied the existing scanner conditions.",
                    )
                )
                continue

            if request.direction is not None and signal.direction != request.direction:
                results.append(
                    ScanResult(
                        symbol=signal.symbol,
                        outcome="skipped",
                        mode=signal.mode,
                        timeframe=signal.timeframe,
                        direction=signal.direction,
                        grade=signal.grade,
                        strategy="EMA/RSI trend evaluation",
                        reason=signal.reason,
                        rejection_reason=f"Result did not match requested direction {request.direction.value}.",
                        metrics=ScanMetrics(**signal.metrics),
                    )
                )
                continue

            if request.grade is not None and signal.grade != request.grade:
                results.append(
                    ScanResult(
                        symbol=signal.symbol,
                        outcome="skipped",
                        mode=signal.mode,
                        timeframe=signal.timeframe,
                        direction=signal.direction,
                        grade=signal.grade,
                        strategy="EMA/RSI trend evaluation",
                        reason=signal.reason,
                        rejection_reason=f"Result did not match requested grade {request.grade.value}.",
                        metrics=ScanMetrics(**signal.metrics),
                    )
                )
                continue

            results.append(
                ScanResult(
                    symbol=signal.symbol,
                    outcome="actionable",
                    mode=signal.mode,
                    timeframe=signal.timeframe,
                    direction=signal.direction,
                    grade=signal.grade,
                    strategy="EMA/RSI trend evaluation",
                    reason=signal.reason,
                    metrics=ScanMetrics(**signal.metrics),
                )
            )

        counts = ScanCounts(total=len(results))
        for result in results:
            setattr(counts, result.outcome, getattr(counts, result.outcome) + 1)

        return ScanResponse(
            message="Scan completed.",
            data=ScanData(
                mode=selected_mode,
                timeframe=selected_timeframe,
                counts=counts,
                results=results,
            ),
        )
