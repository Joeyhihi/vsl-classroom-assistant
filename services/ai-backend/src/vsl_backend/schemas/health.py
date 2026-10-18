"""Health contract (docs/API_CONTRACTS.md#health-p1).

Mirrored by hand in apps/web/src/api/types.ts until Phase 3 code generation;
tests/contract_examples/health.mock.json is checked by both sides.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from vsl_backend.config import Environment, ModelMode

ComponentStatus = Literal["ready", "loading", "unavailable", "disabled", "mock"]


class ComponentHealth(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    status: ComponentStatus
    detail: str | None = None


class HealthComponents(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    sign_model: ComponentHealth
    stt: ComponentHealth
    tts: ComponentHealth


class HealthResponse(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    status: Literal["ok", "degraded"]
    version: str
    api_version: Literal["v1"]
    environment: Environment
    model_mode: ModelMode
    components: HealthComponents
