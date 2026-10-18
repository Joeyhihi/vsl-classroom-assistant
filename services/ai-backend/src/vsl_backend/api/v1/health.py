"""GET /api/v1/health."""

from __future__ import annotations

from fastapi import APIRouter, Request

from vsl_backend import __version__
from vsl_backend.config import Settings
from vsl_backend.recognition.classifiers import Classifier, MockClassifier
from vsl_backend.schemas.health import ComponentHealth, HealthComponents, HealthResponse

router = APIRouter()

_NOT_YET = {"template": "not implemented until Phase 3", "onnx": "not implemented until Phase 5"}


def _sign_model_health(settings: Settings, classifier: Classifier | None) -> ComponentHealth:
    if isinstance(classifier, MockClassifier):
        return ComponentHealth(status="mock", detail=f"scripted predictions ({classifier.script})")
    if classifier is None:
        return ComponentHealth(
            status="unavailable", detail=_NOT_YET.get(settings.model_mode, "no model loaded")
        )
    return ComponentHealth(status="ready", detail=f"model_id={classifier.model_id}")


def build_health(settings: Settings, classifier: Classifier | None) -> HealthResponse:
    components = HealthComponents(
        sign_model=_sign_model_health(settings, classifier),
        stt=(
            ComponentHealth(status="unavailable", detail="not implemented until Phase 7")
            if settings.stt_enabled
            else ComponentHealth(status="disabled")
        ),
        tts=ComponentHealth(status="disabled", detail="browser speechSynthesis is used"),
    )
    degraded = any(
        c.status == "unavailable" for c in (components.sign_model, components.stt, components.tts)
    )
    return HealthResponse(
        status="degraded" if degraded else "ok",
        version=__version__,
        api_version="v1",
        environment=settings.env,
        model_mode=settings.model_mode,
        components=components,
    )


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return build_health(request.app.state.settings, request.app.state.classifier)
