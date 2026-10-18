"""Serve the built SPA from the backend (P9): one origin, one process, one command.

Enabled by `VSL_SERVE_WEB=true` (scripts/run_app.py sets it). Files come only
from `apps/web/dist`. Any other non-API path returns `index.html`, so client-side
views survive a reload. `/api/*` is never shadowed: unknown API paths stay 404
with the error envelope.

The page gets its own CSP. MediaPipe needs WebAssembly (`'wasm-unsafe-eval'`),
and push-to-talk loads its AudioWorklet from a `blob:` URL. Connections stay
limited to this origin and loopback WebSockets (docs/SECURITY_AND_PRIVACY.md).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response

from vsl_backend.config import Settings
from vsl_backend.errors import AppError
from vsl_backend.schemas.common import ErrorCode

logger = logging.getLogger(__name__)

PAGE_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'wasm-unsafe-eval' blob:; "
    "worker-src 'self' blob:; "
    "connect-src 'self' ws://127.0.0.1:* ws://localhost:*; "
    "img-src 'self' data: blob:; "
    "media-src 'self' blob:; "
    "style-src 'self' 'unsafe-inline'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

IMMUTABLE = "public, max-age=31536000, immutable"  # Vite's hashed /assets/ files


def web_unavailable_reason(settings: Settings) -> str | None:
    if not settings.serve_web:
        return "VSL_SERVE_WEB is false"
    if not (settings.web_dist_dir / "index.html").is_file():
        return f"{settings.web_dist_dir} has no index.html (run: npm run build in apps/web)"
    return None


def install_static_web(app: FastAPI, settings: Settings) -> None:
    reason = web_unavailable_reason(settings)
    if reason:
        if settings.serve_web:
            logger.warning("web app not served: %s", reason)
        return
    root = settings.web_dist_dir.resolve()
    index = root / "index.html"

    def page(path: Path, cache: str) -> Response:
        response = FileResponse(path)
        response.headers["Content-Security-Policy"] = PAGE_CONTENT_SECURITY_POLICY
        response.headers["Cache-Control"] = cache
        return response

    @app.get("/{path:path}", include_in_schema=False)
    async def web(request: Request, path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            raise AppError(ErrorCode.NOT_FOUND, "Not found", 404)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            cache = IMMUTABLE if path.startswith("assets/") else "no-cache"
            return page(candidate, cache)
        if Path(path).suffix and not path.endswith(".html"):
            # A missing file (e.g. a MediaPipe asset), not a client-side view.
            raise AppError(ErrorCode.NOT_FOUND, "Not found", 404)
        return page(index, "no-cache")

    logger.info("serving the web app from %s", root)
