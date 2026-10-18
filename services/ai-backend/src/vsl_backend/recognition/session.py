"""Recognition session protocol (docs/API_CONTRACTS.md § WebSocket).

One session per WebSocket connection. This class is transport-free: each call
returns the messages to send and an optional close code, so the protocol is
unit-tested without a socket. Values from frames are never logged.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, ValidationError

from vsl_backend.config import Settings
from vsl_backend.extraction.server_extractor import BinaryFrame, parse_binary_frame
from vsl_backend.recognition.classifiers import Classifier
from vsl_backend.recognition.pipeline import RecognitionPipeline
from vsl_backend.schemas.common import ErrorCode
from vsl_backend.schemas.recognition import (
    CLIENT_MESSAGE,
    PROTOCOL_VERSION,
    ErrorMessage,
    FeatureSpecWire,
    FramesBatch,
    Ping,
    Pong,
    ServerState,
    SessionLimits,
    SessionStart,
    SessionStarted,
    SessionStop,
    SessionStopped,
    StatusMessage,
)
from vsl_features import FEATURE_SPEC
from vsl_features.frames import Frame, FrameError, frame_to_wire, parse_frame


class CloseCode:
    NORMAL = 1000
    POLICY = 1008
    TOO_BIG = 1009
    INTERNAL = 1011
    PROTOCOL_MISMATCH = 4001
    FEATURE_SPEC_MISMATCH = 4002
    RATE_LIMITED = 4003
    HEARTBEAT_TIMEOUT = 4004
    EXTRACTION_UNAVAILABLE = 4005
    MODEL_UNAVAILABLE = 4006


STATUS_MIN_INTERVAL_S = 0.25  # status messages: on change, at most 4/s


@dataclass
class Outcome:
    messages: list[BaseModel] = field(default_factory=list)
    close_code: int | None = None


class Extractor(Protocol):
    """What the session needs from an L3 extractor (see extraction/server_extractor.py)."""

    def extract(self, frame: BinaryFrame) -> Frame: ...


def _fatal(code: ErrorCode, message: str, close_code: int) -> Outcome:
    return Outcome([ErrorMessage(code=code, message=message, fatal=True)], close_code)


class RecognitionSession:
    def __init__(
        self,
        settings: Settings,
        classifier: Classifier | None,
        extractor_factory: Callable[[], Extractor] | None = None,
        extraction_unavailable: str | None = "server extraction is disabled",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._classifier = classifier
        self._extractor_factory = extractor_factory
        self._extraction_unavailable = extraction_unavailable
        self._clock = clock
        self._started_at: float | None = None
        self._mode: str | None = None
        self._pipeline: RecognitionPipeline | None = None
        self._extractor: Extractor | None = None
        self._last_t_ms = -1.0
        self._frame_times: deque[float] = deque()
        self._state: ServerState | None = None
        self._sent_state: tuple[ServerState, bool, bool] | None = None
        self._last_status_at = float("-inf")
        self._hands_visible = False
        self._pose_visible = False
        self.dropped_frames = 0
        self.session_id = f"s_{uuid.uuid4().hex[:12]}"

    @property
    def started(self) -> bool:
        return self._pipeline is not None

    @property
    def max_fps(self) -> int:
        s = self._settings
        return s.max_fps_server_extraction if self._mode == "server" else s.max_fps

    # --- entry points ---------------------------------------------------------

    def handle_text(self, text: str) -> Outcome:
        if len(text.encode("utf-8")) > self._settings.ws_max_message_bytes:
            return _fatal(ErrorCode.PAYLOAD_TOO_LARGE, "Message too large", CloseCode.TOO_BIG)
        try:
            message = CLIENT_MESSAGE.validate_python(json.loads(text))
        except (json.JSONDecodeError, ValidationError):
            return _fatal(ErrorCode.VALIDATION_ERROR, "Invalid message", CloseCode.POLICY)

        if isinstance(message, Ping):
            return Outcome([Pong()])
        if isinstance(message, SessionStart):
            return self._start(message)
        if not self.started:
            return _fatal(ErrorCode.VALIDATION_ERROR, "Send session.start first", CloseCode.POLICY)
        if isinstance(message, SessionStop):
            return Outcome([SessionStopped(reason="client_stop")], CloseCode.NORMAL)
        assert isinstance(message, FramesBatch)
        if self._mode != "client":
            return _fatal(
                ErrorCode.VALIDATION_ERROR, "JSON frames need client mode", CloseCode.POLICY
            )
        if len(message.frames) > self._settings.max_batch:
            return _fatal(ErrorCode.VALIDATION_ERROR, "Batch too large", CloseCode.POLICY)
        return self._handle_frames(message.frames)

    def handle_binary(self, data: bytes) -> Outcome:
        if len(data) > self._settings.ws_max_binary_bytes:
            return _fatal(ErrorCode.PAYLOAD_TOO_LARGE, "Frame too large", CloseCode.TOO_BIG)
        if not self.started or self._mode != "server" or self._extractor is None:
            return _fatal(
                ErrorCode.VALIDATION_ERROR, "Binary frames need server mode", CloseCode.POLICY
            )
        outcome = self._rate_check(1)
        if outcome is not None:
            return outcome
        try:
            binary = parse_binary_frame(data, self._settings.ws_max_binary_bytes)
            frame = parse_frame(frame_to_wire(self._extractor.extract(binary)))
        except FrameError:
            self.dropped_frames += 1
            return self._status_outcome(Outcome())
        return self._process([frame])

    def check_timeouts(self) -> Outcome | None:
        if self._started_at is None:
            return None
        if self._clock() - self._started_at >= self._settings.max_session_s:
            return Outcome([SessionStopped(reason="max_duration")], CloseCode.NORMAL)
        return None

    # --- internals ------------------------------------------------------------

    def _start(self, message: SessionStart) -> Outcome:
        if self.started:
            return _fatal(ErrorCode.VALIDATION_ERROR, "Session already started", CloseCode.POLICY)
        if message.protocol_version != PROTOCOL_VERSION:
            return _fatal(
                ErrorCode.PROTOCOL_MISMATCH,
                f"Server speaks protocol {PROTOCOL_VERSION}",
                CloseCode.PROTOCOL_MISMATCH,
            )
        if message.feature_spec_version != FEATURE_SPEC.version:
            return _fatal(
                ErrorCode.FEATURE_SPEC_MISMATCH,
                f"Server feature spec is {FEATURE_SPEC.version}",
                CloseCode.FEATURE_SPEC_MISMATCH,
            )
        if self._classifier is None:
            return _fatal(
                ErrorCode.MODEL_UNAVAILABLE, "No usable sign model", CloseCode.MODEL_UNAVAILABLE
            )
        if message.extraction_mode == "server":
            if self._extraction_unavailable is not None or self._extractor_factory is None:
                reason = self._extraction_unavailable or "server extraction unavailable"
                return _fatal(
                    ErrorCode.EXTRACTION_UNAVAILABLE, reason, CloseCode.EXTRACTION_UNAVAILABLE
                )
            try:
                self._extractor = self._extractor_factory()
            except Exception:  # mediapipe failures must not crash the server
                return _fatal(
                    ErrorCode.EXTRACTION_UNAVAILABLE,
                    "Server extractor failed to start",
                    CloseCode.EXTRACTION_UNAVAILABLE,
                )

        self._mode = message.extraction_mode
        self._started_at = self._clock()
        self._pipeline = RecognitionPipeline(
            self._classifier,
            aspect=message.image_width / message.image_height,
            cooldown_ms=self._settings.cooldown_ms,
        )
        started = SessionStarted(
            session_id=self.session_id,
            extraction_mode=message.extraction_mode,
            model=self._classifier.info,
            feature_spec=FeatureSpecWire.model_validate(FEATURE_SPEC.to_wire()),
            limits=SessionLimits(
                max_fps=self.max_fps,
                max_batch=self._settings.max_batch,
                max_session_s=self._settings.max_session_s,
            ),
        )
        return Outcome([started])

    def _rate_check(self, count: int) -> Outcome | None:
        now = self._clock()
        self._frame_times.extend([now] * count)
        while self._frame_times and now - self._frame_times[0] > 1.0:
            self._frame_times.popleft()
        # Allow one extra batch of burst on top of the nominal rate.
        if len(self._frame_times) > self.max_fps + self._settings.max_batch:
            return _fatal(
                ErrorCode.RATE_LIMITED, "Too many frames per second", CloseCode.RATE_LIMITED
            )
        return None

    def _handle_frames(self, raw_frames: list[dict[str, object]]) -> Outcome:
        outcome = self._rate_check(len(raw_frames))
        if outcome is not None:
            return outcome
        frames = []
        for raw in raw_frames:
            try:
                frames.append(parse_frame(raw))
            except FrameError:
                self.dropped_frames += 1
        return self._process(frames)

    def _process(self, frames: list[Frame]) -> Outcome:
        assert self._pipeline is not None
        outcome = Outcome()
        for frame in frames:
            if frame.t_ms <= self._last_t_ms:
                self.dropped_frames += 1  # t_ms must increase monotonically
                continue
            self._last_t_ms = frame.t_ms
            self._hands_visible = frame.hands_visible
            self._pose_visible = frame.pose is not None
            result = self._pipeline.push(frame)
            self._state = result.state
            if result.prediction is not None:
                outcome.messages.append(result.prediction)
        return self._status_outcome(outcome)

    def _status_outcome(self, outcome: Outcome) -> Outcome:
        if self._state is None:
            return outcome
        snapshot = (self._state, self._hands_visible, self._pose_visible)
        now = self._clock()
        if snapshot != self._sent_state and now - self._last_status_at >= STATUS_MIN_INTERVAL_S:
            self._sent_state = snapshot
            self._last_status_at = now
            outcome.messages.append(
                StatusMessage(
                    state=self._state,
                    hands_visible=self._hands_visible,
                    pose_visible=self._pose_visible,
                    dropped_frames=self.dropped_frames,
                )
            )
        return outcome
