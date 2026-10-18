"""Recorder and review contracts (Phase 4, developer self-recording)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from vsl_backend.schemas.recognition import WireFrame


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Out(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


SampleKind = Literal["target", "distractor", "background"]
ReviewStatusOut = Literal["pending", "accepted", "rejected", "relabelled"]
RejectReason = Literal["wrong_sign", "incomplete", "out_of_frame", "tracking_failure", "other"]


class RecorderVocabularyItem(_Out):
    gloss_id: str
    text_vi: str
    icon: str
    sample_kind: SampleKind


class RecorderConfig(_Out):
    enabled: bool
    reason: str | None = Field(description="Why the recorder is unavailable, if it is")
    third_party_allowed: bool
    data_root: str | None = Field(description="Local DATA_ROOT path (shown to the developer)")
    vocabulary_version: str | None
    developer_only_vocabulary: bool
    items: list[RecorderVocabularyItem]


class SessionCreate(_Strict):
    signer_id: str = Field(max_length=16)
    consent_id: str = Field(max_length=16)
    dominant_hand: Literal["right", "left"] = "right"
    conditions: dict[str, str] = Field(default_factory=dict, max_length=4)
    image_width: int = Field(ge=64, le=4096)
    image_height: int = Field(ge=64, le=4096)
    feature_spec_version: str = Field(max_length=32)
    extractor_version: str = Field(max_length=64)
    extractor_backend: str = Field(max_length=32)


class SessionCreated(_Out):
    session_id: str
    signer_id: str


class SampleCreate(_Strict):
    label: str = Field(max_length=40)
    take_ms: int = Field(ge=500, le=10_000)
    frames: list[dict[str, Any]] = Field(min_length=1, max_length=600)


class SampleCreateContract(_Out):
    """Typed view of `SampleCreate` for code generation."""

    label: str
    take_ms: int
    frames: list[WireFrame]


class SampleSummary(_Out):
    sample_id: str
    session_id: str
    signer_id: str
    label: str = Field(description="Effective label (relabel applied)")
    recorded_label: str
    sample_kind: SampleKind
    status: ReviewStatusOut
    reject_reason: str | None
    n_frames: int
    dropped_frames: int
    fps: float
    take_ms: int
    collected_at: str


class SampleList(_Out):
    samples: list[SampleSummary]


class SampleFrames(_Out):
    sample_id: str
    image_width: int
    image_height: int
    frames: list[WireFrame]


class ReviewCreate(_Strict):
    status: Literal["accepted", "rejected", "relabelled"]
    reviewer: str = Field(max_length=16)
    reject_reason: RejectReason | None = None
    relabel_to: str | None = Field(default=None, max_length=40)
