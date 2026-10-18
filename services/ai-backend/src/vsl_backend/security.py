"""HTTP security middleware: request ids, Origin allow-list, body limit, headers.

WebSocket Origin checks are added with the WS endpoint in Phase 3 (the same
allow-list applies; see docs/SECURITY_AND_PRIVACY.md).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from vsl_backend.config import Settings
from vsl_backend.errors import error_response
from vsl_backend.schemas.common import ErrorCode

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "connect-src 'self' ws://127.0.0.1:* ws://localhost:*; "
    "img-src 'self' data: blob:; "
    "media-src 'self' blob:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}

CallNext = Callable[[Request], Awaitable[Response]]


def install_security_middleware(app: FastAPI, settings: Settings) -> None:
    allowed_origins = frozenset(settings.allowed_origin_list)
    max_body = settings.max_body_bytes

    @app.middleware("http")
    async def _security(request: Request, call_next: CallNext) -> Response:
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id

        response: Response
        origin = request.headers.get("origin")
        content_length = request.headers.get("content-length")
        if origin is not None and origin not in allowed_origins:
            response = error_response(
                request, ErrorCode.ORIGIN_FORBIDDEN, "Origin not allowed", 403
            )
        elif content_length is not None and (
            not content_length.isdigit() or int(content_length) > max_body
        ):
            response = error_response(
                request,
                ErrorCode.PAYLOAD_TOO_LARGE,
                "Request body too large",
                413,
                {"max_bytes": max_body},
            )
        else:
            response = await call_next(request)

        response.headers["X-Request-ID"] = request_id
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response
