"""Recognition WebSocket and model contracts (docs/API_CONTRACTS.md).

Client messages are validated here; `frames.batch` frames are validated one by
one in `vsl_features.frames` so a bad frame is dropped instead of failing the
whole batch.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from vsl_backend.schemas.common import ErrorCode

PROTOCOL_VERSION = 1

ExtractionMode = Literal["client", "server"]
ModelKind = Literal["mock", "template-dtw", "onnx"]
PredictionStatus = Literal["confident", "uncertain", "rejected"]
ServerState = Literal["waiting_for_hands", "ready", "signing"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Out(BaseModel):
    """Server-produced models: defaulted fields are always present on the wire."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


# --- client → server -------------------------------------------------------


class SessionStart(_Strict):
    type: Literal["session.start"]
    protocol_version: int
    feature_spec_version: str = Field(max_length=32)
    extraction_mode: ExtractionMode = "client"
    image_width: int = Field(ge=64, le=4096)
    image_height: int = Field(ge=64, le=4096)
    fps_hint: int = Field(default=20, ge=1, le=60)
    dominant_hand: Literal["right", "left"] = "right"


class WireFrame(_Out):
    """Contract for one frame. Validated per frame by `vsl_features.frames.parse_frame`
    (so one bad frame is dropped, not the whole batch); exported for the TS client."""

    t_ms: float
    pose: list[list[float]] | None = Field(description="33 x [x, y, z, visibility]")
    left_hand: list[list[float]] | None = Field(description="21 x [x, y, z]; signer's left")
    right_hand: list[list[float]] | None = Field(description="21 x [x, y, z]; signer's right")
    face: list[list[float]] | None = Field(description="K x [x, y, z]; K = len(face_indices)")


class FramesBatch(_Strict):
    type: Literal["frames.batch"]
    frames: list[dict[str, Any]] = Field(min_length=1)


class FramesBatchContract(_Out):
    """Typed view of `FramesBatch` for code generation."""

    type: Literal["frames.batch"]
    frames: list[WireFrame]


class SessionStop(_Strict):
    type: Literal["session.stop"]


class Ping(_Strict):
    type: Literal["ping"]


ClientMessage = Annotated[
    SessionStart | FramesBatch | SessionStop | Ping, Field(discriminator="type")
]
CLIENT_MESSAGE = TypeAdapter[ClientMessage](ClientMessage)


# --- shared --------------------------------------------------------------------


class LabelInfo(_Out):
    gloss_id: str
    text_vi: str
    icon: str


class ModelInfo(_Out):
    model_id: str
    kind: ModelKind
    vocabulary_version: str
    feature_spec_version: str
    developer_only: bool = Field(description="Dev/test model: UI must show a badge")


class FeatureShapes(_Out):
    pose: list[int]
    hand: list[int]
    face: list[int]


class FeatureSpecWire(_Out):
    version: str
    face_indices: list[int]
    shapes: FeatureShapes


class SessionLimits(_Out):
    max_fps: int
    max_batch: int
    max_session_s: int


class VocabularyEntry(_Out):
    gloss_id: str
    text_vi: str
    icon: str


class VocabularyResponse(_Out):
    vocabulary_version: str
    entries: list[VocabularyEntry]


# --- server → client -------------------------------------------------------


class SessionStarted(_Out):
    type: Literal["session.started"] = "session.started"
    session_id: str
    extraction_mode: ExtractionMode
    model: ModelInfo
    feature_spec: FeatureSpecWire
    limits: SessionLimits


class StatusMessage(_Out):
    type: Literal["status"] = "status"
    state: ServerState
    hands_visible: bool
    pose_visible: bool
    dropped_frames: int


class ScoredLabelWire(_Out):
    gloss_id: str
    text_vi: str
    icon: str
    score: float = Field(ge=0, le=1)


class UtteranceSpan(_Out):
    start_ms: float
    end_ms: float
    n_frames: int


class PredictionTimings(_Out):
    hysteresis_ms: float
    inference_ms: float


class PredictionMessage(_Out):
    type: Literal["prediction"] = "prediction"
    prediction_id: str
    model_id: str
    status: PredictionStatus
    utterance: UtteranceSpan
    top: list[ScoredLabelWire]
    timings: PredictionTimings


class ErrorMessage(_Out):
    type: Literal["error"] = "error"
    code: ErrorCode
    message: str
    fatal: bool


class SessionStopped(_Out):
    type: Literal["session.stopped"] = "session.stopped"
    reason: Literal["client_stop", "max_duration"]


class Pong(_Out):
    type: Literal["pong"] = "pong"


ServerMessage = Annotated[
    SessionStarted | StatusMessage | PredictionMessage | ErrorMessage | SessionStopped | Pong,
    Field(discriminator="type"),
]
