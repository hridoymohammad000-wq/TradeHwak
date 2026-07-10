from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock

from app.core.enums import TradingMode
from app.db.repository import PersistenceRepository
from app.services.strategy_service import StrategySignal


class SignalRegistry:
    """Process-wide source of the latest ranked executable strategy signals."""

    MAX_SIGNALS_PER_MODE = 10

    def __init__(self, repository: PersistenceRepository | None = None) -> None:
        self._repository = repository
        self._lock = RLock()
        self._signals: dict[TradingMode, list[StrategySignal]] = {}
        self._updated_at: dict[TradingMode, str] = {}

    @staticmethod
    def _score(signal: StrategySignal) -> float:
        try:
            return float(signal.metrics.get("final_score", 0.0))
        except (AttributeError, TypeError, ValueError):
            return 0.0

    def replace(self, mode: TradingMode, signals: list[StrategySignal], source: str) -> None:
        ranked = sorted(
            signals,
            key=lambda signal: (self._score(signal), signal.symbol),
            reverse=True,
        )[: self.MAX_SIGNALS_PER_MODE]
        timestamp = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._signals[mode] = ranked
            self._updated_at[mode] = timestamp

        if self._repository is not None:
            self._repository.append_log(
                "signal_logs",
                "signal_registry_updated",
                {
                    "mode": mode.value,
                    "source": source,
                    "evaluated_count": len(signals),
                    "published_count": len(ranked),
                    "updated_at": timestamp,
                    "signals": [
                        {
                            "rank": index,
                            "symbol": signal.symbol,
                            "direction": signal.direction.value,
                            "grade": signal.grade.value,
                            "timeframe": signal.timeframe.value,
                            "status": signal.status,
                            "entry_price": signal.entry_price,
                            "current_price": signal.current_price,
                            "score": self._score(signal),
                            "reason": signal.reason,
                        }
                        for index, signal in enumerate(ranked, start=1)
                    ],
                },
            )

    def get(self, mode: TradingMode) -> list[StrategySignal]:
        with self._lock:
            return list(self._signals.get(mode, []))

    def updated_at(self, mode: TradingMode) -> str | None:
        with self._lock:
            return self._updated_at.get(mode)
