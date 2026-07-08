from pydantic import BaseModel, model_validator

from app.schemas.common import ApiResponse


class EngineControlRequest(BaseModel):
    scalping_engine_enabled: bool | None = None
    intraday_engine_enabled: bool | None = None
    auto_trade_enabled: bool | None = None
    emergency_stop: bool | None = None

    @model_validator(mode="after")
    def validate_not_empty(self) -> "EngineControlRequest":
        if not self.model_fields_set:
            raise ValueError("At least one engine control field must be provided.")
        return self


class EngineControlState(BaseModel):
    scalping_engine_enabled: bool
    intraday_engine_enabled: bool
    auto_trade_enabled: bool
    emergency_stop: bool


class EngineControlResponse(ApiResponse[EngineControlState]):
    data: EngineControlState
