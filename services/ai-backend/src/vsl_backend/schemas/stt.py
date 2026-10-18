"""Speech-to-text contracts (P7, gated)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class TranscriptSegment(_Out):
    start_ms: int
    end_ms: int
    text: str


class TranscriptionResponse(_Out):
    text: str
    segments: list[TranscriptSegment]
    duration_ms: int
    model_id: str
    processing_ms: int
