from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _coerce_error_message(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict) and "msg" in first:
            return str(first["msg"])
    return "Request failed."


def _normalize_error_location(loc: tuple[object, ...]) -> str:
    parts = [str(part) for part in loc if part != "body"]
    return ".".join(parts) if parts else "request"


async def http_exception_handler(
    _request: Request, exc: HTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": _coerce_error_message(exc.detail),
            "data": None,
        },
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "field": _normalize_error_location(error["loc"]),
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Request validation failed.",
            "data": {"errors": errors},
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
