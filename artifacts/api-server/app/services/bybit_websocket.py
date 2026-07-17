from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

try:
    import websocket
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    websocket = None


@dataclass(frozen=True)
class BybitWebSocketSnapshot:
    payload: dict[str, Any]
    received_at: float


class BybitWebSocketManager:
    PUBLIC_TESTNET_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
    PUBLIC_MAINNET_URL = "wss://stream.bybit.com/v5/public/linear"
    PRIVATE_DEMO_URL = "wss://stream-demo.bybit.com/v5/private"
    PRIVATE_TESTNET_URL = "wss://stream-testnet.bybit.com/v5/private"
    PRIVATE_MAINNET_URL = "wss://stream.bybit.com/v5/private"

    def __init__(self, service) -> None:
        self._service = service
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._public_thread: threading.Thread | None = None
        self._private_thread: threading.Thread | None = None
        self._public_ws = None
        self._private_ws = None
        self._public_symbols: set[str] = {"BTCUSDT"}
        self._subscribed_public_topics: set[str] = set()
        self._ticker_cache: dict[str, BybitWebSocketSnapshot] = {}
        self._orderbook_cache: dict[str, BybitWebSocketSnapshot] = {}
        self._position_cache: dict[str, BybitWebSocketSnapshot] = {}
        self._order_cache: dict[str, deque[dict[str, Any]]] = {}
        self._execution_cache: deque[dict[str, Any]] = deque(maxlen=500)
        self._public_connected = False
        self._private_connected = False
        self._private_authenticated = False

    def start(self) -> None:
        if websocket is None or self._stop_event.is_set():
            return
        with self._lock:
            if self._public_thread is None or not self._public_thread.is_alive():
                self._public_thread = threading.Thread(
                    target=self._run_public_forever,
                    name="bybit-public-ws",
                    daemon=True,
                )
                self._public_thread.start()
            if self._service.has_private_credentials():
                if self._private_thread is None or not self._private_thread.is_alive():
                    self._private_thread = threading.Thread(
                        target=self._run_private_forever,
                        name="bybit-private-ws",
                        daemon=True,
                    )
                    self._private_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for ws_client in (self._public_ws, self._private_ws):
            try:
                if ws_client is not None:
                    ws_client.close()
            except Exception:
                logger.debug("Bybit websocket close failed", exc_info=True)

    def ensure_public_symbol(self, symbol: str) -> None:
        normalized = str(symbol or "").upper().strip()
        if not normalized:
            return
        topic_args = [f"tickers.{normalized}", f"orderbook.1.{normalized}"]
        with self._lock:
            self._public_symbols.add(normalized)
            ws_client = self._public_ws
            if not self._public_connected or ws_client is None:
                return
            missing = [topic for topic in topic_args if topic not in self._subscribed_public_topics]
            if not missing:
                return
            try:
                ws_client.send(json.dumps({"op": "subscribe", "args": missing}))
                self._subscribed_public_topics.update(missing)
            except Exception:
                logger.warning("Failed to subscribe public websocket topics for %s", normalized, exc_info=True)

    def get_market_snapshot(self, symbol: str) -> dict[str, Any] | None:
        normalized = str(symbol or "").upper().strip()
        with self._lock:
            ticker = self._ticker_cache.get(normalized)
            orderbook = self._orderbook_cache.get(normalized)
        if ticker is None and orderbook is None:
            return None

        ticker_payload = dict(ticker.payload) if ticker else {}
        orderbook_payload = dict(orderbook.payload) if orderbook else {}
        best_bid = self._best_price(orderbook_payload.get("b"), fallback=ticker_payload.get("bid1Price"))
        best_ask = self._best_price(orderbook_payload.get("a"), fallback=ticker_payload.get("ask1Price"))
        return {
            "symbol": normalized,
            "lastPrice": ticker_payload.get("lastPrice"),
            "markPrice": ticker_payload.get("markPrice"),
            "indexPrice": ticker_payload.get("indexPrice"),
            "price24hPcnt": ticker_payload.get("price24hPcnt"),
            "volume24h": ticker_payload.get("volume24h"),
            "turnover24h": ticker_payload.get("turnover24h"),
            "bid1Price": best_bid,
            "ask1Price": best_ask,
            "fetchedAt": max(
                ticker.received_at if ticker else 0.0,
                orderbook.received_at if orderbook else 0.0,
            ),
        }

    def get_open_positions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(snapshot.payload) for snapshot in self._position_cache.values()]

    def get_position(self, symbol: str) -> dict[str, Any] | None:
        normalized = str(symbol or "").upper().strip()
        with self._lock:
            snapshot = self._position_cache.get(normalized)
            return dict(snapshot.payload) if snapshot else None

    def get_order_history(
        self,
        *,
        symbol: str,
        order_id: str | None,
        order_link_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        normalized = str(symbol or "").upper().strip()
        with self._lock:
            rows = list(self._order_cache.get(normalized, deque()))
        if order_id:
            rows = [row for row in rows if str(row.get("orderId") or "").strip() == str(order_id)]
        if order_link_id:
            rows = [row for row in rows if str(row.get("orderLinkId") or "").strip() == str(order_link_id)]
        return rows[: max(limit, 1)]

    def recent_executions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._execution_cache)[: max(limit, 1)]

    def public_connected(self) -> bool:
        with self._lock:
            return self._public_connected

    def private_connected(self) -> bool:
        with self._lock:
            return self._private_connected and self._private_authenticated

    def _run_public_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                ws_client = websocket.WebSocketApp(
                    self._public_url(),
                    on_open=self._on_public_open,
                    on_message=self._on_public_message,
                    on_close=self._on_public_close,
                    on_error=self._on_public_error,
                )
                self._public_ws = ws_client
                ws_client.run_forever(
                    ping_interval=20,
                    ping_timeout=10,
                    skip_utf8_validation=True,
                )
            except Exception:
                logger.warning("Bybit public websocket loop crashed", exc_info=True)
            finally:
                with self._lock:
                    self._public_connected = False
                    self._subscribed_public_topics.clear()
                self._public_ws = None
            if not self._stop_event.is_set():
                time.sleep(2)

    def _run_private_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                ws_client = websocket.WebSocketApp(
                    self._private_url(),
                    on_open=self._on_private_open,
                    on_message=self._on_private_message,
                    on_close=self._on_private_close,
                    on_error=self._on_private_error,
                )
                self._private_ws = ws_client
                ws_client.run_forever(
                    ping_interval=20,
                    ping_timeout=10,
                    skip_utf8_validation=True,
                )
            except Exception:
                logger.warning("Bybit private websocket loop crashed", exc_info=True)
            finally:
                with self._lock:
                    self._private_connected = False
                    self._private_authenticated = False
                self._private_ws = None
            if not self._stop_event.is_set():
                time.sleep(2)

    def _on_public_open(self, ws_client) -> None:
        with self._lock:
            self._public_connected = True
            topics = self._public_topics()
            self._subscribed_public_topics = set(topics)
        ws_client.send(json.dumps({"op": "subscribe", "args": topics}))

    def _on_private_open(self, ws_client) -> None:
        api_key, api_secret = self._service.private_credentials()
        expires = int((time.time() + 20) * 1000)
        signature = hmac.new(
            api_secret.encode("utf-8"),
            f"GET/realtime{expires}".encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        with self._lock:
            self._private_connected = True
            self._private_authenticated = False
        ws_client.send(
            json.dumps(
                {
                    "req_id": "private-auth",
                    "op": "auth",
                    "args": [api_key, expires, signature],
                }
            )
        )

    def _on_public_message(self, _ws_client, message: str) -> None:
        payload = self._decode(message)
        if not payload:
            return
        topic = str(payload.get("topic") or "")
        data = payload.get("data")
        received_at = time.time()
        if topic.startswith("tickers.") and isinstance(data, dict):
            symbol = str(data.get("symbol") or topic.split(".")[-1]).upper()
            with self._lock:
                self._ticker_cache[symbol] = BybitWebSocketSnapshot(
                    payload=data,
                    received_at=received_at,
                )
            return
        if topic.startswith("orderbook.") and isinstance(data, dict):
            symbol = str(data.get("s") or topic.split(".")[-1]).upper()
            with self._lock:
                self._orderbook_cache[symbol] = BybitWebSocketSnapshot(
                    payload=data,
                    received_at=received_at,
                )

    def _on_private_message(self, ws_client, message: str) -> None:
        payload = self._decode(message)
        if not payload:
            return
        op = str(payload.get("op") or "")
        if op == "auth":
            if payload.get("success") is True:
                with self._lock:
                    self._private_authenticated = True
                ws_client.send(json.dumps({"op": "subscribe", "args": ["position", "order", "execution"]}))
            return
        topic = str(payload.get("topic") or "")
        rows = payload.get("data")
        if not isinstance(rows, list):
            return
        received_at = time.time()
        if topic == "position":
            self._ingest_positions(rows, received_at)
            return
        if topic == "order":
            self._ingest_orders(rows)
            return
        if topic == "execution":
            self._ingest_executions(rows)

    def _ingest_positions(self, rows: list[dict[str, Any]], received_at: float) -> None:
        with self._lock:
            for row in rows:
                symbol = str(row.get("symbol") or "").upper().strip()
                if not symbol:
                    continue
                self._position_cache[symbol] = BybitWebSocketSnapshot(
                    payload=dict(row),
                    received_at=received_at,
                )

    def _ingest_orders(self, rows: list[dict[str, Any]]) -> None:
        with self._lock:
            for row in rows:
                symbol = str(row.get("symbol") or "").upper().strip()
                if not symbol:
                    continue
                book = self._order_cache.setdefault(symbol, deque(maxlen=50))
                row_order_id = str(row.get("orderId") or "").strip()
                row_link_id = str(row.get("orderLinkId") or "").strip()
                existing = next(
                    (
                        index
                        for index, existing_row in enumerate(book)
                        if (
                            row_order_id
                            and str(existing_row.get("orderId") or "").strip() == row_order_id
                        ) or (
                            row_link_id
                            and str(existing_row.get("orderLinkId") or "").strip() == row_link_id
                        )
                    ),
                    None,
                )
                if existing is not None:
                    book[existing] = dict(row)
                else:
                    book.appendleft(dict(row))

    def _ingest_executions(self, rows: list[dict[str, Any]]) -> None:
        with self._lock:
            for row in rows:
                exec_id = str(row.get("execId") or "").strip()
                if exec_id and any(str(existing.get("execId") or "").strip() == exec_id for existing in self._execution_cache):
                    continue
                self._execution_cache.appendleft(dict(row))

    def _on_public_close(self, _ws_client, _code, _message) -> None:
        with self._lock:
            self._public_connected = False

    def _on_private_close(self, _ws_client, _code, _message) -> None:
        with self._lock:
            self._private_connected = False
            self._private_authenticated = False

    @staticmethod
    def _on_public_error(_ws_client, error: Exception) -> None:
        logger.debug("Bybit public websocket error: %s", error)

    @staticmethod
    def _on_private_error(_ws_client, error: Exception) -> None:
        logger.debug("Bybit private websocket error: %s", error)

    def _public_topics(self) -> list[str]:
        args: list[str] = []
        for symbol in sorted(self._public_symbols):
            args.append(f"tickers.{symbol}")
            args.append(f"orderbook.1.{symbol}")
        return args

    def _public_url(self) -> str:
        # Bybit Demo uses the mainnet public market-data stream and the
        # dedicated Demo private stream. Only a true testnet account uses
        # the testnet public host.
        return self.PUBLIC_TESTNET_URL if self._service.uses_testnet_streams() else self.PUBLIC_MAINNET_URL

    def _private_url(self) -> str:
        if self._service.uses_demo_streams():
            return self.PRIVATE_DEMO_URL
        return self.PRIVATE_TESTNET_URL if self._service.uses_testnet_streams() else self.PRIVATE_MAINNET_URL

    @staticmethod
    def _decode(message: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _best_price(levels: Any, *, fallback: Any) -> str | None:
        if isinstance(levels, list) and levels:
            first = levels[0]
            if isinstance(first, list) and first:
                return str(first[0])
        if fallback is not None:
            return str(fallback)
        return None
