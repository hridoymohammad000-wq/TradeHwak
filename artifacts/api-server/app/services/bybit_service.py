import hashlib
import hmac
import json
import os
import re
import time
from decimal import Decimal
from urllib import error, parse, request

from fastapi import HTTPException, status

from app.schemas.bybit import (
    BybitConfigStatusData,
    BybitConfigStatusResponse,
    BybitConnectionStatusData,
    BybitConnectionStatusResponse,
    BybitMarketSnapshotData,
    BybitMarketSnapshotResponse,
    BybitMarketServiceStatus,
    BybitMarketTestData,
    BybitMarketTestResponse,
)
from app.services.bybit_websocket import BybitWebSocketManager


class BybitService:
    REQUIRED_ENV = "demo"
    REQUIRED_BASE_URL = "https://api-demo.bybit.com"
    RECV_WINDOW = "20000"

    def __init__(self) -> None:
        self._symbol_validation_cache: dict[str, tuple[dict, float]] = {}
        self._websocket_manager = BybitWebSocketManager(self)

    def get_config_status(self) -> BybitConfigStatusResponse:
        api_key = (os.environ.get("BYBIT_DEMO_API_KEY") or "").strip()
        api_secret = (os.environ.get("BYBIT_DEMO_API_SECRET") or "").strip()
        environment = (os.environ.get("BYBIT_ENV") or self.REQUIRED_ENV).strip()
        base_url = (os.environ.get("BYBIT_BASE_URL") or self.REQUIRED_BASE_URL).strip()
        return BybitConfigStatusResponse(
            message="Bybit config status fetched successfully.",
            data=BybitConfigStatusData(
                environment=environment,
                base_url=base_url,
                api_key_configured=bool(api_key),
                api_secret_configured=bool(api_secret),
                configured=bool(api_key and api_secret),
            ),
        )

    def get_connection_status(self) -> BybitConnectionStatusResponse:
        result = self._connection_test()
        return BybitConnectionStatusResponse(
            success=result["code"] == "CONNECTED",
            message="Bybit connection status fetched successfully.",
            data=BybitConnectionStatusData(
                code=result["code"],
                status=result["status"],
                detail=result["detail"],
                equity=result.get("equity"),
                available_balance=result.get("availableBalance"),
                fetched_at=result.get("fetchedAt"),
            ),
        )

    def get_market_test(self, symbol: str | None) -> BybitMarketTestResponse:
        target = symbol or "BTCUSDT"
        results = {
            "symbol": target,
            "services": {},
            "testedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        for name, call in [
            ("instruments", lambda: self._validate_symbol(target)),
            ("m1Klines", lambda: self._get_closed_klines(target, "1")),
            ("m5Klines", lambda: self._get_closed_klines(target, "5")),
            ("ticker", lambda: self._get_ticker(target)),
            ("orderbook", lambda: self._get_orderbook(target)),
        ]:
            try:
                payload = call()
                extra = {}
                if name in {"m1Klines", "m5Klines"}:
                    extra["count"] = len(payload["result"]["list"])
                results["services"][name] = {"status": "CONNECTED", **extra}
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, str) else "Bybit request failed"
                results["services"][name] = {
                    "status": "ERROR",
                    "code": f"HTTP_{exc.status_code}",
                    "detail": detail,
                }

        all_passed = all(item["status"] == "CONNECTED" for item in results["services"].values())
        return BybitMarketTestResponse(
            success=all_passed,
            message="Bybit market test completed.",
            data=BybitMarketTestData(
                symbol=results["symbol"],
                tested_at=results["testedAt"],
                all_passed=all_passed,
                services={
                    key: BybitMarketServiceStatus(**value)
                    for key, value in results["services"].items()
                },
            ),
        )

    def get_market_snapshot(self, symbol: str | None) -> BybitMarketSnapshotResponse:
        target = symbol or "BTCUSDT"
        self._websocket_manager.ensure_public_symbol(target)
        cached = self._websocket_manager.get_market_snapshot(target)
        if cached is None:
            ticker = self._get_ticker(target)
            orderbook = self._get_orderbook(target)
            ticker_item = ticker.get("result", {}).get("list", [{}])[0]
            book = orderbook.get("result", {}) or {}
            bids = book.get("b") or []
            asks = book.get("a") or []
            best_bid = float(bids[0][0]) if bids else None
            best_ask = float(asks[0][0]) if asks else None
            fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        else:
            ticker_item = cached
            best_bid = self._to_float(cached.get("bid1Price"))
            best_ask = self._to_float(cached.get("ask1Price"))
            fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(cached.get("fetchedAt") or time.time()))
        spread = (best_ask - best_bid) if best_bid is not None and best_ask is not None else None
        spread_percent = (
            round((spread / best_bid) * 100, 4)
            if spread is not None and best_bid not in (None, 0)
            else None
        )

        return BybitMarketSnapshotResponse(
            message="Bybit market snapshot fetched successfully.",
            data=BybitMarketSnapshotData(
                symbol=ticker_item.get("symbol", target),
                last_price=self._to_float(ticker_item.get("lastPrice")),
                mark_price=self._to_float(ticker_item.get("markPrice")),
                index_price=self._to_float(ticker_item.get("indexPrice")),
                price_change_percent_24h=self._to_float(ticker_item.get("price24hPcnt")),
                volume_24h=self._to_float(ticker_item.get("volume24h")),
                turnover_24h=self._to_float(ticker_item.get("turnover24h")),
                best_bid_price=best_bid,
                best_ask_price=best_ask,
                spread=spread,
                spread_percent=spread_percent,
                fetched_at=fetched_at,
            ),
        )

    def get_closed_closes(self, symbol: str, interval: str, limit: int = 121) -> list[float]:
        klines = self._get_closed_klines(symbol, interval, limit=limit)
        rows = list(reversed(klines.get("result", {}).get("list", [])))
        closes: list[float] = []
        for row in rows:
            try:
                closes.append(float(row[4]))
            except (TypeError, ValueError, IndexError):
                continue
        return closes

    def get_top_volume_symbols(self, limit: int = 8) -> list[str]:
        data = self._public_get(
            "/v5/market/tickers",
            parse.urlencode({"category": "linear"}),
        )
        rows = data.get("result", {}).get("list", []) or []
        ranked: list[tuple[str, float]] = []

        for row in rows:
            symbol = str(row.get("symbol") or "").upper()
            if not symbol.endswith("USDT"):
                continue
            if row.get("status") not in (None, "", "Trading"):
                continue
            try:
                turnover = float(row.get("turnover24h") or 0)
            except (TypeError, ValueError):
                continue
            if turnover <= 0:
                continue
            ranked.append((symbol, turnover))

        ranked.sort(key=lambda item: item[1], reverse=True)
        return [symbol for symbol, _ in ranked[: max(limit, 1)]]

    def get_validated_symbol(self, symbol: str) -> dict:
        return self._validate_symbol(symbol)

    def get_raw_ticker(self, symbol: str) -> dict:
        return self._get_ticker(symbol)

    def get_wallet_snapshot(self) -> dict[str, Decimal]:
        wallet = self._private_get("/v5/account/wallet-balance", "accountType=UNIFIED&coin=USDT")
        wallet_list = wallet.get("result", {}).get("list", [{}])
        coins = wallet_list[0].get("coin", []) if wallet_list else []
        coin = next((item for item in coins if item.get("coin") == "USDT"), {})
        equity = Decimal(str(coin.get("equity") or "0"))
        available = Decimal(
            str(
                coin.get("availableToWithdraw")
                or coin.get("availableBalance")
                or coin.get("equity")
                or "0"
            )
        )
        return {"equity": equity, "available": available}

    def create_private_order(self, payload: dict) -> dict:
        return self._private_post("/v5/order/create", payload)

    def get_open_positions(self) -> list[dict]:
        cached = self._websocket_manager.get_open_positions()
        if cached:
            return cached
        data = self._private_get(
            "/v5/position/list",
            parse.urlencode({"category": "linear", "settleCoin": "USDT"}),
        )
        return data.get("result", {}).get("list", []) or []

    def get_position(self, symbol: str) -> dict | None:
        target = str(symbol or "").upper()
        cached = self._websocket_manager.get_position(target)
        if cached is not None:
            size = self._to_float(cached.get("size")) or 0.0
            if size > 0:
                return cached
        for position in self.get_open_positions():
            if str(position.get("symbol") or "").upper() != target:
                continue
            size = self._to_float(position.get("size")) or 0.0
            if size <= 0:
                continue
            return position
        return None

    def get_order_history(
        self,
        *,
        symbol: str,
        order_id: str | None = None,
        order_link_id: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        cached = self._websocket_manager.get_order_history(
            symbol=symbol,
            order_id=order_id,
            order_link_id=order_link_id,
            limit=limit,
        )
        if cached:
            return cached
        query = {
            "category": "linear",
            "symbol": str(symbol or "").upper(),
            "limit": str(max(limit, 1)),
        }
        if order_id:
            query["orderId"] = str(order_id)
        if order_link_id:
            query["orderLinkId"] = str(order_link_id)
        data = self._private_get("/v5/order/history", parse.urlencode(query))
        return data.get("result", {}).get("list", []) or []

    def emergency_close_position(
        self,
        *,
        symbol: str,
        side: str,
        qty: str,
        order_link_id: str,
    ) -> dict:
        return self.create_private_order(
            {
                "category": "linear",
                "symbol": str(symbol or "").upper(),
                "side": side,
                "orderType": "Market",
                "qty": qty,
                "timeInForce": "IOC",
                "positionIdx": 0,
                "reduceOnly": True,
                "closeOnTrigger": False,
                "orderLinkId": order_link_id,
            }
        )

    def get_closed_pnls(self, limit: int = 50) -> list[dict]:
        data = self._private_get(
            "/v5/position/closed-pnl",
            parse.urlencode({"category": "linear", "limit": str(limit)}),
        )
        return data.get("result", {}).get("list", []) or []

    def start_websockets(self) -> None:
        self._websocket_manager.start()

    def stop_websockets(self) -> None:
        self._websocket_manager.stop()

    def uses_testnet_streams(self) -> bool:
        return "testnet" in self._base_url()

    def uses_demo_streams(self) -> bool:
        return "api-demo.bybit.com" in self._base_url()

    def has_private_credentials(self) -> bool:
        api_key = (os.environ.get("BYBIT_DEMO_API_KEY") or "").strip()
        api_secret = (os.environ.get("BYBIT_DEMO_API_SECRET") or "").strip()
        return bool(api_key and api_secret)

    def private_credentials(self) -> tuple[str, str]:
        return self._credentials()

    def _base_url(self) -> str:
        return (os.environ.get("BYBIT_BASE_URL") or self.REQUIRED_BASE_URL).strip()

    def _assert_demo_configuration(self) -> None:
        configured_env = (os.environ.get("BYBIT_ENV") or self.REQUIRED_ENV).strip()
        base_url = self._base_url()
        if configured_env != self.REQUIRED_ENV or base_url != self.REQUIRED_BASE_URL:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Bybit Demo requires BYBIT_ENV=demo and "
                    f"BYBIT_BASE_URL={self.REQUIRED_BASE_URL}"
                ),
            )

    def _credentials(self) -> tuple[str, str]:
        self._assert_demo_configuration()
        api_key = (os.environ.get("BYBIT_DEMO_API_KEY") or "").strip()
        api_secret = (os.environ.get("BYBIT_DEMO_API_SECRET") or "").strip()
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Bybit Demo API key and secret are not configured.",
            )
        return api_key, api_secret

    @staticmethod
    def _signature(payload: str, secret: str) -> str:
        return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _to_float(value: str | float | int | None) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _fetch_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        method: str = "GET",
        body: dict | str | None = None,
        timeout: int = 8,
    ) -> dict:
        data = None
        if body is not None:
            if isinstance(body, str):
                data = body.encode("utf-8")
            else:
                data = json.dumps(body).encode("utf-8")
        req = request.Request(url, headers=headers or {}, method=method, data=data)
        try:
            with request.urlopen(req, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Bybit returned invalid JSON.",
            ) from exc
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            try:
                data = json.loads(raw)
                detail = data.get("retMsg") or raw
            except Exception:
                detail = raw or str(exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Bybit HTTP {exc.code}: {detail}",
            ) from exc
        except error.URLError as exc:
            detail = str(exc.reason)
            if "timed out" in detail.lower():
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Bybit market data request timed out.",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unable to reach Bybit: {detail}",
            ) from exc
        except TimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Bybit market data request timed out.",
            ) from exc

    def _public_get(self, endpoint: str, query: str) -> dict:
        self._assert_demo_configuration()
        data = self._fetch_json(f"{self._base_url()}{endpoint}?{query}")
        if data.get("retCode") != 0:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=data.get("retMsg") or "Bybit public endpoint failed.",
            )
        return data

    def _private_get(self, endpoint: str, query: str = "") -> dict:
        api_key, api_secret = self._credentials()
        timestamp = str(self._get_server_timestamp())
        signature = self._signature(timestamp + api_key + self.RECV_WINDOW + query, api_secret)
        headers = {
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": self.RECV_WINDOW,
        }
        data = self._fetch_json(
            f"{self._base_url()}{endpoint}{'?' + query if query else ''}",
            headers=headers,
        )
        if data.get("retCode") != 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Bybit Demo authentication failed: {data.get('retMsg') or 'Unknown error'}",
            )
        return data

    def _private_post(self, endpoint: str, body: dict) -> dict:
        api_key, api_secret = self._credentials()
        timestamp = str(self._get_server_timestamp())
        body_text = json.dumps(body, separators=(",", ":"))
        signature = self._signature(timestamp + api_key + self.RECV_WINDOW + body_text, api_secret)
        headers = {
            "Content-Type": "application/json",
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": self.RECV_WINDOW,
        }
        data = self._fetch_json(
            f"{self._base_url()}{endpoint}",
            headers=headers,
            method="POST",
            body=body_text,
        )
        if data.get("retCode") != 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Bybit Demo order rejected: {data.get('retMsg') or 'Unknown error'}",
            )
        return data

    def _get_server_timestamp(self) -> int:
        data = self._fetch_json(f"{self._base_url()}/v5/market/time", timeout=5)
        time_second = data.get("result", {}).get("timeSecond")
        time_nano = data.get("result", {}).get("timeNano")

        if time_nano is not None:
            return int(str(time_nano)[:13])
        if time_second is not None:
            return int(time_second) * 1000
        return int(time.time() * 1000)

    def _validate_symbol(self, symbol: str) -> dict:
        candidate = str(symbol or "BTCUSDT").upper().strip()
        if not re.fullmatch(r"[A-Z0-9]{4,20}", candidate):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Symbol must be an uppercase Bybit linear USDT perpetual code.",
            )
        if not candidate.endswith("USDT"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only USDT-settled perpetual symbols are supported.",
            )

        now = time.time()
        cached = self._symbol_validation_cache.get(candidate)
        if cached and now < cached[1]:
            return cached[0]

        data = self._public_get(
            "/v5/market/instruments-info",
            parse.urlencode({"category": "linear", "symbol": candidate}),
        )
        instruments = data.get("result", {}).get("list", [])
        instrument = instruments[0] if instruments else None
        if not instrument or instrument.get("symbol") != candidate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bybit linear perpetual instrument not found for {candidate}.",
            )
        result = {"symbol": candidate, "instrument": instrument}
        self._symbol_validation_cache[candidate] = (result, now + 600)
        return result

    def _get_closed_klines(self, symbol: str, interval: str, limit: int = 121) -> dict:
        validated = self._validate_symbol(symbol)
        requested_limit = max(1, min(int(limit), 1000))
        interval_ms = int(interval) * 60_000
        fetch_limit = min(requested_limit + 2, 1000)
        data = self._public_get(
            "/v5/market/kline",
            parse.urlencode(
                {
                    "category": "linear",
                    "symbol": validated["symbol"],
                    "interval": interval,
                    "limit": fetch_limit,
                }
            ),
        )
        now_ms = int(time.time() * 1000)
        closed = [
            row
            for row in (data.get("result", {}).get("list") or [])
            if int(row[0]) + interval_ms <= now_ms
        ][:requested_limit]
        return {"retCode": 0, "result": {"list": closed}}

    def _get_ticker(self, symbol: str) -> dict:
        validated = self._validate_symbol(symbol)
        data = self._public_get(
            "/v5/market/tickers",
            parse.urlencode({"category": "linear", "symbol": validated["symbol"]}),
        )
        if not data.get("result", {}).get("list"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ticker unavailable for {validated['symbol']}.",
            )
        return data

    def _get_orderbook(self, symbol: str) -> dict:
        validated = self._validate_symbol(symbol)
        return self._public_get(
            "/v5/market/orderbook",
            parse.urlencode({"category": "linear", "symbol": validated["symbol"], "limit": 25}),
        )

    def _connection_test(self) -> dict:
        try:
            wallet = self._private_get("/v5/account/wallet-balance", "accountType=UNIFIED&coin=USDT")
            wallet_list = wallet.get("result", {}).get("list", [{}])
            coins = wallet_list[0].get("coin", []) if wallet_list else []
            coin = next((item for item in coins if item.get("coin") == "USDT"), {})
            return {
                "code": "CONNECTED",
                "status": "Bybit Demo Connected",
                "detail": "Authenticated private wallet balance verification succeeded.",
                "equity": coin.get("equity", "0"),
                "availableBalance": coin.get("availableToWithdraw")
                or coin.get("availableBalance")
                or coin.get("equity", "0"),
                "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "Bybit connection failed."
            if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
                return {
                    "code": "NOT_CONFIGURED",
                    "status": "Bybit Demo Not Configured",
                    "detail": detail,
                    "equity": None,
                    "availableBalance": None,
                    "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            return {
                "code": "ERROR",
                "status": "Bybit Demo Unavailable",
                "detail": detail,
                "equity": None,
                "availableBalance": None,
                "fetchedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
