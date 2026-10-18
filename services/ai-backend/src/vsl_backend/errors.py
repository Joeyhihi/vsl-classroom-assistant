"""Application errors and the handlers that render the error envelope."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from vsl_backend.inference.resource_manager import ResourceExhausted
from vsl_backend.schemas.common import ErrorBody, ErrorCode, ErrorResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def request_id_of(request: Request) -> str | None:
    rid = getattr(request.state, "request_id", None)
    return rid if isinstance(rid, str) else None


def error_response(
    request: Request,
    code: ErrorCode,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    rid = request_id_of(request)
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, details=details or {}, request_id=rid)
    )
    headers = {"X-Request-ID": rid} if rid else None
    return JSONResponse(body.model_dump(mode="json"), status_code=status_code, headers=headers)


_HTTP_STATUS_CODES = {
    404: ErrorCode.NOT_FOUND,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    429: ErrorCode.RATE_LIMITED,
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(request, exc.code, exc.message, exc.status_code, exc.details)

    @app.exception_handler(ResourceExhausted)
    async def _resource_exhausted(request: Request, exc: ResourceExhausted) -> JSONResponse:
        return error_response(
            request,
            ErrorCode.RESOURCE_EXHAUSTED,
            str(exc),
            503,
            {"available_mb": round(exc.available_mb), "required_mb": round(exc.required_mb)},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field locations and messages only; never echo submitted values.
        errors = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", "")} for e in exc.errors()]
        return error_response(
            request,
            ErrorCode.VALIDATION_ERROR,
            "Request validation failed",
            422,
            {"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_STATUS_CODES.get(exc.status_code, ErrorCode.VALIDATION_ERROR)
        if exc.status_code >= 500:
            code = ErrorCode.INTERNAL
        return error_response(request, code, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error request_id=%s", request_id_of(request))
        return error_response(request, ErrorCode.INTERNAL, "Internal server error", 500)
