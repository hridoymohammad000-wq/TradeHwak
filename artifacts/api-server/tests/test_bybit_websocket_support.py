import unittest
from unittest.mock import patch

from app.services.bybit_service import BybitService


class StubBybitService(BybitService):
    def __init__(self) -> None:
        super().__init__()
        self.ticker_calls = 0
        self.orderbook_calls = 0
        self.private_get_calls = 0

    def _get_ticker(self, symbol: str) -> dict:
        self.ticker_calls += 1
        return {
            "result": {
                "list": [
                    {
                        "symbol": symbol,
                        "lastPrice": "100.5",
                        "markPrice": "100.4",
                        "indexPrice": "100.3",
                        "price24hPcnt": "0.01",
                        "volume24h": "1000",
                        "turnover24h": "100000",
                        "bid1Price": "100.4",
                        "ask1Price": "100.5",
                    }
                ]
            }
        }

    def _get_orderbook(self, symbol: str) -> dict:
        self.orderbook_calls += 1
        return {
            "result": {
                "b": [["100.4", "1"]],
                "a": [["100.5", "1"]],
            }
        }

    def _private_get(self, endpoint: str, query: str = "") -> dict:
        self.private_get_calls += 1
        if "position/list" in endpoint:
            return {
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "size": "1",
                            "markPrice": "101",
                            "avgPrice": "100",
                            "stopLoss": "99",
                            "takeProfit": "103",
                        }
                    ]
                }
            }
        if "order/history" in endpoint:
            return {
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "orderId": "rest-order",
                            "orderLinkId": "rest-link",
                            "orderStatus": "Filled",
                        }
                    ]
                }
            }
        return {"result": {"list": []}}


class BybitWebSocketSupportTests(unittest.TestCase):
    def test_demo_mode_uses_demo_private_and_testnet_public_hosts(self):
        service = StubBybitService()

        self.assertTrue(service.uses_demo_streams())
        self.assertFalse(service.uses_testnet_streams())
        self.assertEqual(
            service._websocket_manager._public_url(),
            "wss://stream.bybit.com/v5/public/linear",
        )
        self.assertEqual(
            service._websocket_manager._private_url(),
            "wss://stream-demo.bybit.com/v5/private",
        )

    def test_market_snapshot_uses_websocket_cache_when_available(self):
        service = StubBybitService()
        manager = service._websocket_manager
        manager._ingest_positions([], 0.0)
        manager._on_public_message(
            None,
            '{"topic":"tickers.BTCUSDT","type":"snapshot","data":{"symbol":"BTCUSDT","lastPrice":"101.2","markPrice":"101.1","indexPrice":"101.0","price24hPcnt":"0.02","volume24h":"1500","turnover24h":"120000","bid1Price":"101.1","ask1Price":"101.2"}}',
        )
        manager._on_public_message(
            None,
            '{"topic":"orderbook.1.BTCUSDT","type":"snapshot","data":{"s":"BTCUSDT","b":[["101.1","2"]],"a":[["101.2","3"]]}}',
        )

        response = service.get_market_snapshot("BTCUSDT")

        self.assertEqual(response.data.symbol, "BTCUSDT")
        self.assertEqual(response.data.last_price, 101.2)
        self.assertEqual(response.data.best_bid_price, 101.1)
        self.assertEqual(service.ticker_calls, 0)
        self.assertEqual(service.orderbook_calls, 0)

    def test_private_cache_is_preferred_for_positions_and_orders(self):
        service = StubBybitService()
        manager = service._websocket_manager
        manager._ingest_positions(
            [
                {
                    "symbol": "BTCUSDT",
                    "size": "2",
                    "markPrice": "102",
                    "avgPrice": "100",
                    "stopLoss": "98",
                    "takeProfit": "104",
                }
            ],
            1.0,
        )
        manager._ingest_orders(
            [
                {
                    "symbol": "BTCUSDT",
                    "orderId": "ws-order",
                    "orderLinkId": "ws-link",
                    "orderStatus": "Filled",
                }
            ]
        )

        position = service.get_position("BTCUSDT")
        rows = service.get_order_history(symbol="BTCUSDT", order_link_id="ws-link", limit=5)

        self.assertEqual(position["size"], "2")
        self.assertEqual(rows[0]["orderId"], "ws-order")
        self.assertEqual(service.private_get_calls, 0)

    def test_main_lifespan_starts_and_stops_websockets(self):
        from app import main

        with patch.object(main.bybit_service, "start_websockets") as start_ws, patch.object(
            main.bybit_service, "stop_websockets"
        ) as stop_ws, patch.object(main, "_initialize_runtime_state"), patch.object(
            main, "_auto_trade_loop"
        ) as auto_loop, patch.object(main, "_trade_management_loop") as management_loop, patch.object(
            main, "_exchange_reconciliation_loop"
        ) as reconciliation_loop:
            auto_loop.return_value = management_loop.return_value = reconciliation_loop.return_value = None

            async def runner():
                async with main.lifespan(main.app):
                    pass

            import asyncio

            asyncio.run(runner())

        start_ws.assert_called_once()
        stop_ws.assert_called_once()


if __name__ == "__main__":
    unittest.main()
