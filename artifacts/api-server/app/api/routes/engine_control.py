from fastapi import APIRouter

from app.core.enums import TradingMode
from app.core.state import auto_trade_service, engine_service, settings_service
from app.schemas.engine import EngineControlRequest, EngineControlResponse
from app.schemas.settings import SettingsUpdate


router = APIRouter(tags=["Engine"])


@router.post(
    "/engine/control",
    response_model=EngineControlResponse,
    summary="Update engine controls",
    description="Safely updates engine and execution control flags.",
)
def update_engine_controls(payload: EngineControlRequest) -> EngineControlResponse:
    return engine_service.update_controls(payload)


@router.post(
    "/bot/start",
    response_model=EngineControlResponse,
    summary="Start intraday automatic trading flow",
    description=(
        "Forces Intraday as the active strategy, keeps the Scalping engine "
        "disabled, enables the Intraday engine and auto trade, then immediately "
        "runs one Intraday scan-signal-risk-execution-management cycle."
    ),
)
def start_bot() -> EngineControlResponse:
    # Existing installations may still have Scalping persisted as the active
    # strategy. Normalize the durable settings first so the Intraday-only start
    # cannot fail or accidentally re-enable Scalping.
    settings_service.update_settings(
        SettingsUpdate(
            active_strategy_mode=TradingMode.INTRADAY,
            scalping_engine_enabled=False,
            intraday_engine_enabled=True,
            auto_trade_enabled=False,
            emergency_stop=False,
        )
    )
    response = engine_service.update_controls(
        EngineControlRequest(
            scalping_engine_enabled=False,
            intraday_engine_enabled=True,
            auto_trade_enabled=True,
            emergency_stop=False,
        )
    )
    auto_trade_service.run_cycle()
    return response


@router.post(
    "/bot/stop",
    response_model=EngineControlResponse,
    summary="Stop automatic trading",
    description="Disables auto trade without closing or modifying open positions.",
)
def stop_bot() -> EngineControlResponse:
    return engine_service.update_controls(
        EngineControlRequest(auto_trade_enabled=False)
    )
