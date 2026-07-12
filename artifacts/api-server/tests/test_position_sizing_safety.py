import unittest
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException

from app.core.enums import TradingMode
from app.services.manual_trade_service import ManualTradeService


class ActiveTradesStub:
    def __init__(self, *, notional=0.0, planned_risk=0.0):
        trade = SimpleNamespace(notional=notional, planned_risk_usdt=planned_risk)
        self.data = SimpleNamespace(
            scalping_trades=[trade] if notional or planned_risk else [],
            intraday_trades=[],
        )


class TradeServiceStub:
    def __init__(self, *, notional=0.0, planned_risk=0.0, remaining_loss=50.0):
        self._active = ActiveTradesStub(notional=notional, planned_risk=planned_risk)
        self.remaining_loss = remaining_loss

    def get_active_trades(self):
        return self._active

    def get_remaining_daily_loss_budget(self, configured_daily_max_loss):
        return min(float(configured_daily_max_loss), self.remaining_loss)


class PositionSizingSafetyTests(unittest.TestCase):
    def _service(self, *, notional=0.0, planned_risk=0.0, remaining_loss=50.0):
        service = ManualTradeService.__new__(ManualTradeService)
        service._trade_service = TradeServiceStub(
            notional=notional,
            planned_risk=planned_risk,
            remaining_loss=remaining_loss,
        )
        return service

    def test_required_margin_must_fit_available_balance(self):
        service = self._service()

        with self.assertRaises(HTTPException) as context:
            service._validate_margin_and_exposure(
                mode=TradingMode.SCALPING,
                account_equity=Decimal("100"),
                available_balance=Decimal("5"),
                notional=Decimal("60"),
                planned_risk=Decimal("1"),
            )

        self.assertIn("Required margin", context.exception.detail)

    def test_total_exposure_must_include_existing_open_positions(self):
        service = self._service(notional=Decimal("960"))

        with self.assertRaises(HTTPException) as context:
            service._validate_margin_and_exposure(
                mode=TradingMode.SCALPING,
                account_equity=Decimal("100"),
                available_balance=Decimal("50"),
                notional=Decimal("50"),
                planned_risk=Decimal("1"),
            )

        self.assertIn("exposure cap", context.exception.detail)

    def test_existing_open_risk_reduces_new_risk_capacity(self):
        service = self._service(planned_risk=Decimal("45"), remaining_loss=50.0)

        with self.assertRaises(HTTPException) as context:
            service._validate_margin_and_exposure(
                mode=TradingMode.SCALPING,
                account_equity=Decimal("1000"),
                available_balance=Decimal("500"),
                notional=Decimal("100"),
                planned_risk=Decimal("10"),
            )

        self.assertIn("remaining risk capacity", context.exception.detail)


if __name__ == "__main__":
    unittest.main()
