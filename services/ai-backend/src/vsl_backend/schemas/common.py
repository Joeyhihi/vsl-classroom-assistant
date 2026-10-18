"""Shared schemas: the error envelope (docs/API_CONTRACTS.md#error-envelope)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    RATE_LIMITED = "RATE_LIMITED"
    ORIGIN_FORBIDDEN = "ORIGIN_FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
    FEATURE_SPEC_MISMATCH = "FEATURE_SPEC_MISMATCH"
    EXTRACTION_UNAVAILABLE = "EXTRACTION_UNAVAILABLE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    STT_UNAVAILABLE = "STT_UNAVAILABLE"
    RECORDER_DISABLED = "RECORDER_DISABLED"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    INTERNAL = "INTERNAL"


class ErrorBody(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    error: ErrorBody
