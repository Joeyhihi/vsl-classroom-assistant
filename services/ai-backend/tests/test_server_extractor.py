from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from vsl_backend.extraction.server_extractor import (
    BINARY_HEADER,
    BinaryFrame,
    ServerLandmarkExtractor,
    decode_jpeg,
    extraction_unavailable_reason,
    parse_binary_frame,
    result_to_frame,
)
from vsl_features import FEATURE_SPEC
from vsl_features.frames import FrameError


def jpeg(width: int = 64, height: int = 48) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (120, 80, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_parse_binary_frame() -> None:
    data = BINARY_HEADER.pack(1234, 64, 48) + jpeg()
    frame = parse_binary_frame(data, 200_000)
    assert (frame.t_ms, frame.width, frame.height) == (1234.0, 64, 48)
    assert BINARY_HEADER.size == 16


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"short", "too short"),
        (BINARY_HEADER.pack(1, 0, 48) + b"\xff\xd8", "dimensions"),
        (BINARY_HEADER.pack(1, 1920, 1080) + b"\xff\xd8", "dimensions"),
        (BINARY_HEADER.pack(1, 64, 48) + b"\x89PNG", "not a JPEG"),
        (BINARY_HEADER.pack(1, 64, 48) + b"\xff\xd8" + b"x" * 300, "too large"),
    ],
)
def test_parse_binary_frame_rejects(data: bytes, message: str) -> None:
    with pytest.raises(FrameError, match=message):
        parse_binary_frame(data, 200)


def test_decode_jpeg() -> None:
    image = decode_jpeg(jpeg(), 64, 48)
    assert image.shape == (48, 64, 3) and image.dtype == np.uint8
    with pytest.raises(FrameError, match="does not match"):
        decode_jpeg(jpeg(), 32, 48)
    with pytest.raises(FrameError, match="could not be decoded"):
        decode_jpeg(b"\xff\xd8garbage", 64, 48)


@dataclass
class Lm:
    x: float
    y: float
    z: float
    visibility: float | None = None


def landmarks(n: int, vis: float | None = None, x: float = 0.5) -> list[Lm]:
    return [Lm(x + i * 1e-3, 0.4, 0.0, vis) for i in range(n)]


def pose_with_wrists(vis: float | None = 0.9) -> list[Lm]:
    """Signer's left wrist (15) on the image's right, right wrist (16) on the left."""
    pose = landmarks(33, vis)
    pose[15] = Lm(0.7, 0.5, 0.0, vis)
    pose[16] = Lm(0.3, 0.5, 0.0, vis)
    return pose


@dataclass
class FakeResult:
    pose_landmarks: object
    left_hand_landmarks: object
    right_hand_landmarks: object
    face_landmarks: object


@pytest.mark.parametrize("nested", [False, True])
def test_result_to_frame_accepts_both_result_shapes(nested: bool) -> None:
    def wrap(items: list[Lm]) -> object:
        return [items] if nested else items

    result = FakeResult(
        wrap(pose_with_wrists()), [], wrap(landmarks(21, x=0.3)), wrap(landmarks(478))
    )
    frame = result_to_frame(result, 10.0)

    assert (
        frame.pose is not None
        and frame.pose.shape == (33, 4)
        and frame.pose[0, 3] == pytest.approx(0.9)
    )
    assert frame.left_hand is None
    assert frame.right_hand is not None and frame.right_hand.shape == (21, 3)
    assert frame.face is not None and frame.face.shape == FEATURE_SPEC.face_shape
    assert frame.face[0, 0] == pytest.approx(0.5 + FEATURE_SPEC.face_indices[0] * 1e-3)


def test_missing_pose_visibility_counts_as_visible() -> None:
    frame = result_to_frame(FakeResult(landmarks(33, None), [], [], []), 0.0)
    assert frame.pose is not None and frame.pose[11, 3] == 1.0


class FakeLandmarker:
    def __init__(self) -> None:
        self.timestamps: list[int] = []

    def detect_for_video(self, image: np.ndarray, timestamp_ms: int) -> FakeResult:
        self.timestamps.append(timestamp_ms)
        return FakeResult(landmarks(33, 0.9), [], [], [])


def test_extractor_uses_strictly_increasing_timestamps() -> None:
    fake = FakeLandmarker()
    extractor = ServerLandmarkExtractor(Path("unused.task"), landmarker_factory=lambda _: fake)
    for t in (100.0, 100.4, 99.0):
        extractor.extract(BinaryFrame(t, 64, 48, jpeg()))
    assert fake.timestamps == [100, 101, 102]


def test_unavailable_reasons(tmp_path: Path) -> None:
    assert "disabled" in (extraction_unavailable_reason(False, tmp_path) or "")
    # mediapipe is never installed on the dev Mac or in CI (optional extra).
    assert "mediapipe" in (extraction_unavailable_reason(True, tmp_path / "x.task") or "")


def test_hands_follow_the_pose_wrists_not_mediapipe_naming() -> None:
    # MediaPipe called the hand near the signer's RIGHT wrist "left": geometry wins.
    result = FakeResult(pose_with_wrists(), landmarks(21, x=0.31), [], [])
    frame = result_to_frame(result, 0.0)
    assert frame.left_hand is None
    assert frame.right_hand is not None and frame.right_hand[0, 0] == pytest.approx(0.31)
