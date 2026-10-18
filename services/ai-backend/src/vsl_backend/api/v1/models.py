"""GET /api/v1/vocabulary, /api/v1/models and /api/v1/diagnostics."""

from __future__ import annotations

import platform

import psutil
from fastapi import APIRouter, Request
from pydantic import BaseModel

from vsl_backend.errors import AppError
from vsl_backend.extraction.server_extractor import extraction_unavailable_reason
from vsl_backend.recognition.classifiers import Classifier
from vsl_backend.schemas.common import ErrorCode
from vsl_backend.schemas.recognition import (
    FeatureSpecWire,
    ModelInfo,
    VocabularyEntry,
    VocabularyResponse,
)
from vsl_features import FEATURE_SPEC

router = APIRouter()


class ServerExtractionInfo(BaseModel):
    available: bool
    reason: str | None


class DiagnosticsResponse(BaseModel):
    rss_mb: float
    python_version: str
    platform: str
    model: ModelInfo | None
    server_extraction: ServerExtractionInfo


def _classifier(request: Request) -> Classifier:
    classifier: Classifier | None = request.app.state.classifier
    if classifier is None:
        raise AppError(ErrorCode.MODEL_UNAVAILABLE, "No usable sign model", 503)
    return classifier


@router.get("/vocabulary", response_model=VocabularyResponse)
async def vocabulary(request: Request) -> VocabularyResponse:
    classifier = _classifier(request)
    return VocabularyResponse(
        vocabulary_version=classifier.info.vocabulary_version,
        entries=[
            VocabularyEntry(gloss_id=label.gloss_id, text_vi=label.text_vi, icon=label.icon)
            for label in classifier.labels
            if not label.gloss_id.startswith("__")
        ],
    )


@router.get("/models", response_model=ModelInfo)
async def models(request: Request) -> ModelInfo:
    return _classifier(request).info


@router.get("/feature-spec", response_model=FeatureSpecWire)
async def feature_spec() -> FeatureSpecWire:
    """The landmark layout the browser must send (same as in session.started)."""
    return FeatureSpecWire.model_validate(FEATURE_SPEC.to_wire())


@router.get("/diagnostics", response_model=DiagnosticsResponse)
async def diagnostics(request: Request) -> DiagnosticsResponse:
    """Local performance diagnostics (backend memory, extraction availability)."""
    settings = request.app.state.settings
    classifier: Classifier | None = request.app.state.classifier
    reason = extraction_unavailable_reason(
        settings.server_extraction_enabled, settings.holistic_model_path
    )
    return DiagnosticsResponse(
        rss_mb=round(psutil.Process().memory_info().rss / 2**20, 1),
        python_version=platform.python_version(),
        platform=f"{platform.system()} {platform.machine()}",
        model=classifier.info if classifier else None,
        server_extraction=ServerExtractionInfo(available=reason is None, reason=reason),
    )
