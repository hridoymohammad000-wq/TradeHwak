from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock

from app.core.enums import TradingMode
from app.db.repository import PersistenceRepository
from app.services.strategy_service import StrategySignal


class SignalRegistry:
    """Process-wide source of the latest evaluated strategy signals."""

    def __init__(self, repository: PersistenceRepository | None = None) -> None:
        self._repository = repository
        self._lock = RLock()
        self._signals: dict[TradingMode, list[StrategySignal]] = {}
        self._updated_at: dict[TradingMode, str] = {}

    def replace(self, mode: TradingMode, signals: list[StrategySignal], source: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._signals[mode] = list(signals)
            self._updated_at[mode] = timestamp

        if self._repository is not None:
            self._repository.append_log(
                "signal_logs",
                "signal_registry_updated",
                {
                    "mode": mode.value,
                    "source": source,
                    "count": len(signals),
                    "updated_at": timestamp,
                    "signals": [
                        {
                            "symbol": signal.symbol,
                            "direction": signal.direction.value,
                            "grade": signal.grade.value,
                            "timeframe": signal.timeframe.value,
                            "status": signal.status,
                            "entry_price": signal.entry_price,
                            "current_price": signal.current_price,
                            "reason": signal.reason,
                        }
                        for signal in signals
                    ],
                },
            )

    def get(self, mode: TradingMode) -> list[StrategySignal]:
        with self._lock:
            return list(self._signals.get(mode, []))

    def updated_at(self, mode: TradingMode) -> str | None:
        with self._lock:
            return self._updated_at.get(mode)
