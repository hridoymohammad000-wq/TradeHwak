from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import AppConfig


class LocalRuntimeBackend:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def save(self, snapshot: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self._path.parent,
            delete=False,
        ) as handle:
            json.dump(snapshot, handle, indent=2, ensure_ascii=True)
            temp_path = Path(handle.name)
        temp_path.replace(self._path)


class SupabaseRuntimeBackend:
    def __init__(
        self,
        *,
        url: str,
        service_role_key: str,
        table: str,
        row_key: str,
        timeout_seconds: float,
    ) -> None:
        self._base_url = url.rstrip("/")
        self._service_role_key = service_role_key
        self._table = table
        self._row_key = row_key
        self._timeout_seconds = timeout_seconds

    def load(self) -> dict[str, Any]:
        query = urlencode({"key": f"eq.{self._row_key}", "select": "payload"})
        response = self._request("GET", f"/rest/v1/{self._table}?{query}")
        if not isinstance(response, list) or not response:
            return {}
        payload = response[0].get("payload")
        return payload if isinstance(payload, dict) else {}

    def save(self, snapshot: dict[str, Any]) -> None:
        body = {"key": self._row_key, "payload": snapshot}
        query = urlencode({"key": f"eq.{self._row_key}"})
        updated = self._request(
            "PATCH",
            f"/rest/v1/{self._table}?{query}",
            body=body,
            headers={"Prefer": "return=representation"},
        )
        if isinstance(updated, list) and updated:
            return
        self._request(
            "POST",
            f"/rest/v1/{self._table}",
            body=body,
            headers={"Prefer": "return=representation"},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        request_headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
        }
        if headers:
            request_headers.update(headers)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            f"{self._base_url}{path}",
            data=payload,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8").strip()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore").strip()
            raise RuntimeError(
                f"Supabase runtime store request failed with HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Supabase runtime store is unreachable: {exc.reason}") from exc

        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Supabase runtime store returned invalid JSON.") from exc


class RuntimeStore:
    def __init__(self, config: AppConfig) -> None:
        self._lock = RLock()
        self._local_backend = LocalRuntimeBackend(config.runtime_state_path)
        self._remote_backend = (
            SupabaseRuntimeBackend(
                url=config.supabase_url,
                service_role_key=config.supabase_service_role_key,
                table=config.supabase_runtime_table,
                row_key=config.supabase_runtime_row_key,
                timeout_seconds=config.supabase_timeout_seconds,
            )
            if config.supabase_url and config.supabase_service_role_key
            else None
        )
        self._storage_mode = "local"
        self._last_remote_error: str | None = None
        self._snapshot = self._bootstrap_snapshot()

    @property
    def storage_mode(self) -> str:
        return self._storage_mode

    @property
    def last_remote_error(self) -> str | None:
        return self._last_remote_error

    def get_section(self, section: str, default: Any) -> Any:
        with self._lock:
            value = self._snapshot.get(section, default)
            return deepcopy(value)

    def replace_section(self, section: str, value: Any) -> None:
        with self._lock:
            self._snapshot[section] = deepcopy(value)
            self._snapshot["updated_at"] = self._now_iso()
            self._persist_locked()

    def append_event(self, event_type: str, message: str) -> None:
        with self._lock:
            events = list(self._snapshot.get("events", []))
            events.insert(
                0,
                {
                    "event_type": event_type,
                    "message": message,
                    "created_at": self._now_iso(),
                },
            )
            self._snapshot["events"] = events[:50]
            self._snapshot["updated_at"] = self._now_iso()
            self._persist_locked()

    def get_events(self, limit: int = 8) -> list[dict[str, Any]]:
        with self._lock:
            events = self._snapshot.get("events", [])
            return deepcopy(events[:limit]) if isinstance(events, list) else []

    def _bootstrap_snapshot(self) -> dict[str, Any]:
        local_snapshot = self._normalize_snapshot(self._local_backend.load())
        if self._remote_backend is None:
            return local_snapshot

        try:
            remote_snapshot = self._normalize_snapshot(self._remote_backend.load())
            self._storage_mode = "supabase"
            self._last_remote_error = None
        except RuntimeError as exc:
            self._storage_mode = "local"
            self._last_remote_error = str(exc)
            return local_snapshot

        if self._has_runtime_state(remote_snapshot):
            return remote_snapshot

        if self._has_runtime_state(local_snapshot):
            try:
                self._remote_backend.save(local_snapshot)
                self._storage_mode = "supabase"
                self._last_remote_error = None
            except RuntimeError as exc:
                self._storage_mode = "local"
                self._last_remote_error = str(exc)
            return local_snapshot

        return remote_snapshot

    @staticmethod
    def _has_runtime_state(snapshot: dict[str, Any]) -> bool:
        return any(bool(snapshot.get(section)) for section in ("settings", "trades", "workflow", "events"))

    @staticmethod
    def _normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        base = snapshot if isinstance(snapshot, dict) else {}
        return {
            "settings": base.get("settings", {}),
            "trades": base.get("trades", {}),
            "workflow": base.get("workflow", {}),
            "events": base.get("events", []),
            "updated_at": base.get("updated_at"),
        }

    def _persist_locked(self) -> None:
        snapshot = deepcopy(self._snapshot)
        self._local_backend.save(snapshot)
        if self._remote_backend is None:
            self._storage_mode = "local"
            self._last_remote_error = None
            return
        try:
            self._remote_backend.save(snapshot)
            self._storage_mode = "supabase"
            self._last_remote_error = None
        except RuntimeError as exc:
            self._storage_mode = "local_fallback"
            self._last_remote_error = str(exc)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
