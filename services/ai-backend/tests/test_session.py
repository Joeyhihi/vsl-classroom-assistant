from __future__ import annotations

import json
from typing import Any

import pytest

from tests.conftest import load_replay, make_settings
from vsl_backend.extraction.server_extractor import BINARY_HEADER, BinaryFrame
from vsl_backend.recognition.classifiers import MockClassifier
from vsl_backend.recognition.session import CloseCode, Outcome, RecognitionSession
from vsl_features.frames import Frame, parse_frame


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def start_message(**overrides: Any) -> str:
    return json.dumps(
        {
            "type": "session.start",
            "protocol_version": 1,
            "feature_spec_version": "fs-1",
            "extraction_mode": "client",
            "image_width": 640,
            "image_height": 480,
        }
        | overrides
    )


def batch(frames: list[dict[str, Any]]) -> str:
    return json.dumps({"type": "frames.batch", "frames": frames})


def types(outcome: Outcome) -> list[str]:
    return [m.model_dump()["type"] for m in outcome.messages]


def first(outcome: Outcome) -> dict[str, Any]:
    data: dict[str, Any] = outcome.messages[0].model_dump()
    return data


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def new_session(clock: FakeClock, **settings: Any) -> RecognitionSession:
    return RecognitionSession(make_settings(**settings), MockClassifier(), clock=clock)


def started(clock: FakeClock, **settings: Any) -> RecognitionSession:
    session = new_session(clock, **settings)
    assert types(session.handle_text(start_message())) == ["session.started"]
    return session


def test_handshake_returns_feature_spec_and_limits(clock: FakeClock) -> None:
    session = new_session(clock)
    msg = first(session.handle_text(start_message()))

    assert msg["feature_spec"]["version"] == "fs-1"
    assert msg["feature_spec"]["shapes"] == {"pose": [33, 4], "hand": [21, 3], "face": [40, 3]}
    assert len(msg["feature_spec"]["face_indices"]) == 40
    assert msg["limits"] == {"max_fps": 30, "max_batch": 8, "max_session_s": 7200}
    assert msg["model"]["kind"] == "mock" and msg["model"]["developer_only"]


@pytest.mark.parametrize(
    ("overrides", "code", "close"),
    [
        ({"protocol_version": 2}, "PROTOCOL_MISMATCH", CloseCode.PROTOCOL_MISMATCH),
        (
            {"feature_spec_version": "fs-9"},
            "FEATURE_SPEC_MISMATCH",
            CloseCode.FEATURE_SPEC_MISMATCH,
        ),
        ({"extraction_mode": "server"}, "EXTRACTION_UNAVAILABLE", CloseCode.EXTRACTION_UNAVAILABLE),
        ({"image_width": 10}, "VALIDATION_ERROR", CloseCode.POLICY),
        ({"unexpected": 1}, "VALIDATION_ERROR", CloseCode.POLICY),
    ],
)
def test_start_rejections(
    clock: FakeClock, overrides: dict[str, Any], code: str, close: int
) -> None:
    outcome = new_session(clock).handle_text(start_message(**overrides))

    assert first(outcome)["code"] == code and first(outcome)["fatal"]
    assert outcome.close_code == close


def test_model_unavailable_closes_with_4006(clock: FakeClock) -> None:
    session = RecognitionSession(make_settings(), None, clock=clock)
    outcome = session.handle_text(start_message())
    assert first(outcome)["code"] == "MODEL_UNAVAILABLE" and outcome.close_code == 4006


def test_frames_before_start_and_garbage_are_policy_violations(clock: FakeClock) -> None:
    assert new_session(clock).handle_text(batch([{}])).close_code == CloseCode.POLICY
    assert new_session(clock).handle_text("not json").close_code == CloseCode.POLICY
    assert new_session(clock).handle_text('{"type": "nope"}').close_code == CloseCode.POLICY


def test_ping_and_stop(clock: FakeClock) -> None:
    session = started(clock)
    assert types(session.handle_text('{"type": "ping"}')) == ["pong"]
    stop = session.handle_text('{"type": "session.stop"}')
    assert first(stop) == {"type": "session.stopped", "reason": "client_stop"}
    assert stop.close_code == CloseCode.NORMAL


def test_oversized_message_and_batch(clock: FakeClock) -> None:
    session = started(clock, ws_max_message_bytes=300)
    one_real_frame = load_replay()["frames"][:1]  # ~2 KB of landmarks
    assert session.handle_text(batch(one_real_frame)).close_code == CloseCode.TOO_BIG

    session = started(clock, max_batch=2)
    assert session.handle_text(batch([{"t_ms": 1}] * 3)).close_code == CloseCode.POLICY


def test_invalid_and_non_monotonic_frames_are_dropped_not_fatal(clock: FakeClock) -> None:
    replay = load_replay()
    good = replay["frames"][:3]
    bad = dict(good[0], t_ms=5000, right_hand=[[9.0, 9.0, 0.0]] * 21)
    session = started(clock)

    outcome = session.handle_text(batch([good[1], good[0], bad, good[2]]))

    assert outcome.close_code is None
    assert session.dropped_frames == 2  # good[0] is out of order, `bad` is out of range
    assert first(outcome)["type"] == "status"


def test_rate_limit(clock: FakeClock) -> None:
    session = started(clock, max_fps=10, max_batch=4)
    frames = load_replay()["frames"]
    outcomes = [session.handle_text(batch(frames[i : i + 4])) for i in range(0, 20, 4)]
    assert outcomes[-1].close_code == CloseCode.RATE_LIMITED


def test_status_messages_are_rate_limited(clock: FakeClock) -> None:
    session = started(clock)
    frames = load_replay()["frames"]
    statuses = 0
    for i, raw in enumerate(frames):
        clock.now = i / 100  # 100 fps of wall time, far faster than 4 status/s
        statuses += types(session.handle_text(batch([raw]))).count("status")
    assert statuses <= len(frames) / 100 * 4 + 1


def test_replay_produces_one_prediction_per_synthetic_sign(clock: FakeClock) -> None:
    replay = load_replay()
    session = started(clock)
    predictions = []
    for i in range(0, len(replay["frames"]), 4):
        clock.now += 4 / 15
        outcome = session.handle_text(batch(replay["frames"][i : i + 4]))
        predictions += [
            m.model_dump() for m in outcome.messages if m.model_dump()["type"] == "prediction"
        ]

    assert len(predictions) == len(replay["segments"])
    # Mock classifier: scripted confident → uncertain → rejected.
    assert [p["status"] for p in predictions] == ["confident", "uncertain", "rejected"]
    assert all(500 <= p["timings"]["hysteresis_ms"] <= 800 for p in predictions)


def test_max_session_duration(clock: FakeClock) -> None:
    session = started(clock, max_session_s=10)
    assert session.check_timeouts() is None
    clock.now = 10
    outcome = session.check_timeouts()
    assert outcome is not None and first(outcome)["reason"] == "max_duration"


def test_binary_frames_rejected_in_client_mode(clock: FakeClock) -> None:
    session = started(clock)
    data = BINARY_HEADER.pack(1, 640, 480) + b"\xff\xd8xx"
    assert session.handle_binary(data).close_code == CloseCode.POLICY


class FakeExtractor:
    def __init__(self) -> None:
        self.frames = [parse_frame(f) for f in load_replay()["frames"]]
        self.calls = 0

    def extract(self, frame: BinaryFrame) -> Frame:
        result = self.frames[self.calls % len(self.frames)]
        self.calls += 1
        return Frame(frame.t_ms, result.pose, result.left_hand, result.right_hand, result.face)


def test_server_extraction_mode_with_fake_extractor(clock: FakeClock) -> None:
    extractor = FakeExtractor()
    session = RecognitionSession(
        make_settings(),
        MockClassifier(),
        extractor_factory=lambda: extractor,
        extraction_unavailable=None,
        clock=clock,
    )
    msg = first(session.handle_text(start_message(extraction_mode="server")))
    assert msg["extraction_mode"] == "server" and msg["limits"]["max_fps"] == 20

    predictions = 0
    for i, raw in enumerate(load_replay()["frames"]):
        clock.now = i / 15
        data = BINARY_HEADER.pack(int(raw["t_ms"]) + 1, 640, 480) + b"\xff\xd8jpeg"
        outcome = session.handle_binary(data)
        assert outcome.close_code is None
        predictions += types(outcome).count("prediction")
    assert predictions == 3
    assert session.handle_text(batch([{"t_ms": 1}])).close_code == CloseCode.POLICY
