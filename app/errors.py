from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.errors import ErrorBody, ErrorResponse

log = logging.getLogger("errors")


def _request_id(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)


def _build(
    code: str,
    message: str,
    request_id: Optional[str],
    details: Optional[dict[str, Any]] = None,
) -> dict:
    return ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id, details=details)
    ).model_dump(mode="json")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE",
    }
    code = code_map.get(exc.status_code, "ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=_build(code, str(exc.detail), _request_id(request)),
    )


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_build(
            "VALIDATION_ERROR",
            "Request body validation failed",
            _request_id(request),
            details={"errors": exc.errors()},
        ),
    )


async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_build("INTERNAL_ERROR", "Internal server error", _request_id(request)),
    )


def install(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_handler)  # type: ignore[arg-type]
