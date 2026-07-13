from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class WorkerHealth:
    interval_seconds: int
    started_at: float | None = None
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_error: str | None = None


class RuntimeHealthService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._workers: dict[str, WorkerHealth] = {}

    def register_worker(self, name: str, *, interval_seconds: int) -> None:
        with self._lock:
            self._workers[name] = WorkerHealth(interval_seconds=interval_seconds)

    def mark_started(self, name: str) -> None:
        with self._lock:
            worker = self._workers.get(name)
            if worker is None:
                return
            worker.started_at = time.time()

    def mark_success(self, name: str) -> None:
        with self._lock:
            worker = self._workers.get(name)
            if worker is None:
                return
            now = time.time()
            worker.started_at = worker.started_at or now
            worker.last_success_at = now
            worker.last_error = None

    def mark_failure(self, name: str, error: str) -> None:
        with self._lock:
            worker = self._workers.get(name)
            if worker is None:
                return
            now = time.time()
            worker.started_at = worker.started_at or now
            worker.last_failure_at = now
            worker.last_error = error

    def snapshot(self) -> dict[str, dict[str, bool | str | int | None]]:
        now = time.time()
        with self._lock:
            snapshot: dict[str, dict[str, bool | str | int | None]] = {}
            for name, worker in self._workers.items():
                grace_seconds = max(worker.interval_seconds * 2, 30)
                last_activity = worker.last_success_at or worker.started_at
                is_stale = bool(
                    last_activity is not None and now - last_activity > grace_seconds
                )
                failure_after_success = bool(
                    worker.last_failure_at is not None
                    and (
                        worker.last_success_at is None
                        or worker.last_failure_at > worker.last_success_at
                    )
                )
                ready = bool(
                    worker.started_at is not None
                    and not failure_after_success
                    and not is_stale
                )
                snapshot[name] = {
                    "ready": ready,
                    "interval_seconds": worker.interval_seconds,
                    "last_error": worker.last_error,
                }
            return snapshot
