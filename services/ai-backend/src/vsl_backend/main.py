"""Application factory. Run via `scripts/run_backend.py` (uvicorn factory mode)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vsl_backend import __version__
from vsl_backend.api.v1.router import router as v1_router
from vsl_backend.config import Settings
from vsl_backend.errors import install_error_handlers
from vsl_backend.logging_config import configure_logging
from vsl_backend.recognition.classifiers import build_classifier
from vsl_backend.security import install_security_middleware

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.model_mode == "mock":
            logger.warning("MOCK model mode: predictions are scripted, not real recognition")
        yield

    app = FastAPI(
        title="VSL Classroom Assistant API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.env == "dev" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.env == "dev" else None,
    )
    app.state.settings = settings
    app.state.classifier = build_classifier(settings)

    install_error_handlers(app)
    install_security_middleware(app, settings)
    app.include_router(v1_router)
    return app
