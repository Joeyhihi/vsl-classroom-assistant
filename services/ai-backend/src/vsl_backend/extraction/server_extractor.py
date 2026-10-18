"""L3 server-side landmark extraction (ADR-002 fallback ladder).

The browser sends JPEG frames over the localhost WebSocket only when browser
extraction is too slow and the user confirmed. Frames are decoded and processed
in memory and dropped immediately; nothing is written or logged.

Python MediaPipe is an optional extra (`uv sync --extra server-extraction`) used
on the Windows laptop only. It is imported lazily so the default backend (and
the M1 Mac) never loads it.

UNVERIFIED until the Windows P3 run: the exact Python HolisticLandmarker API in
mediapipe 1.x and its left/right-hand convention. `_landmark_rows` accepts both
"list of landmarks" and "list of lists" result shapes.
"""

from __future__ import annotations

import importlib.util
import io
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from vsl_features import FEATURE_SPEC, FeatureSpec
from vsl_features.frames import Frame, FrameError

# t_ms uint64, width uint16, height uint16, 4 reserved bytes (little-endian).
BINARY_HEADER = struct.Struct("<QHH4x")
MAX_WIDTH, MAX_HEIGHT = 640, 480

RgbImage = NDArray[np.uint8]


@dataclass(frozen=True)
class BinaryFrame:
    t_ms: float
    width: int
    height: int
    jpeg: bytes


def parse_binary_frame(data: bytes, max_bytes: int) -> BinaryFrame:
    if len(data) <= BINARY_HEADER.size:
        raise FrameError("binary frame too short")
    if len(data) > max_bytes:
        raise FrameError("binary frame too large")
    t_ms, width, height = BINARY_HEADER.unpack_from(data)
    if not (0 < width <= MAX_WIDTH and 0 < height <= MAX_HEIGHT):
        raise FrameError("binary frame dimensions out of range")
    jpeg = data[BINARY_HEADER.size :]
    if not jpeg.startswith(b"\xff\xd8"):
        raise FrameError("binary frame is not a JPEG")
    return BinaryFrame(float(t_ms), width, height, jpeg)


def decode_jpeg(jpeg: bytes, width: int, height: int) -> RgbImage:
    from PIL import Image  # part of the server-extraction extra

    try:
        with Image.open(io.BytesIO(jpeg)) as image:
            if image.format != "JPEG":
                raise FrameError("not a JPEG")
            rgb = image.convert("RGB")
    except (OSError, SyntaxError):
        raise FrameError("JPEG could not be decoded") from None
    if rgb.size != (width, height):
        raise FrameError("JPEG size does not match the header")
    return np.asarray(rgb, dtype=np.uint8)


class Landmarker(Protocol):
    def detect_for_video(self, image: RgbImage, timestamp_ms: int) -> Any: ...


def _landmark_rows(value: Any) -> Sequence[Any] | None:
    """MediaPipe returns either a list of landmarks or a list of per-person lists."""
    if not value:
        return None
    first = value[0]
    return first if isinstance(first, list | tuple) else value


def result_to_frame(result: Any, t_ms: float, spec: FeatureSpec = FEATURE_SPEC) -> Frame:
    def array(rows: Sequence[Any] | None, n: int, with_visibility: bool) -> np.ndarray | None:
        if rows is None or len(rows) < n:
            return None
        cols = 4 if with_visibility else 3
        out = np.zeros((n, cols), dtype=np.float32)
        for i, lm in enumerate(rows[:n]):
            out[i, :3] = (lm.x, lm.y, lm.z)
            if with_visibility:
                # Python landmarks may omit visibility; treat missing as visible.
                vis = getattr(lm, "visibility", None)
                out[i, 3] = 1.0 if vis is None else min(max(float(vis), 0.0), 1.0)
        return out

    pose = array(_landmark_rows(getattr(result, "pose_landmarks", None)), spec.pose_shape[0], True)
    face_rows = _landmark_rows(getattr(result, "face_landmarks", None))
    face = None
    if face_rows is not None and len(face_rows) > max(spec.face_indices):
        face = array([face_rows[i] for i in spec.face_indices], len(spec.face_indices), False)
    n_hand = spec.hand_shape[0]
    return Frame(
        t_ms=t_ms,
        pose=pose,
        left_hand=array(
            _landmark_rows(getattr(result, "left_hand_landmarks", None)), n_hand, False
        ),
        right_hand=array(
            _landmark_rows(getattr(result, "right_hand_landmarks", None)), n_hand, False
        ),
        face=face,
    )


def mediapipe_available() -> bool:
    return importlib.util.find_spec("mediapipe") is not None


def extraction_unavailable_reason(enabled: bool, model_path: Path) -> str | None:
    if not enabled:
        return "server extraction is disabled (VSL_SERVER_EXTRACTION_ENABLED=false)"
    if not mediapipe_available():
        return "mediapipe is not installed (uv sync --extra server-extraction)"
    if importlib.util.find_spec("PIL") is None:
        return "pillow is not installed (uv sync --extra server-extraction)"
    if not model_path.is_file():
        return "holistic model not found (bootstrap.py --with-models)"
    return None


def _mediapipe_landmarker(model_path: Path) -> Landmarker:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    options = vision.HolisticLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
    )
    landmarker = vision.HolisticLandmarker.create_from_options(options)

    class _Adapter:
        def detect_for_video(self, image: RgbImage, timestamp_ms: int) -> Any:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
            return landmarker.detect_for_video(mp_image, timestamp_ms)

    return _Adapter()


class ServerLandmarkExtractor:
    """JPEG bytes → `Frame` with the same feature spec as browser extraction."""

    def __init__(
        self,
        model_path: Path,
        landmarker_factory: Callable[[Path], Landmarker] = _mediapipe_landmarker,
        decoder: Callable[[bytes, int, int], RgbImage] = decode_jpeg,
    ) -> None:
        self._landmarker = landmarker_factory(model_path)
        self._decoder = decoder
        self._last_ts = -1

    def extract(self, frame: BinaryFrame) -> Frame:
        image = self._decoder(frame.jpeg, frame.width, frame.height)
        # VIDEO mode requires strictly increasing integer timestamps.
        ts = max(int(frame.t_ms), self._last_ts + 1)
        self._last_ts = ts
        result = self._landmarker.detect_for_video(image, ts)
        return result_to_frame(result, frame.t_ms)
