from pydantic import BaseModel

from app.core.enums import RuntimeMode, TradingMode
from app.schemas.common import ApiResponse


class ModeData(BaseModel):
    system_mode: RuntimeMode
    available_system_modes: list[RuntimeMode]
    active_strategy_mode: TradingMode
    available_strategy_modes: list[TradingMode]


class ModeResponse(ApiResponse[ModeData]):
    data: ModeData
