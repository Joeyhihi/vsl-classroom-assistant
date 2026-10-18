"""Per-frame normalisation into a fixed-length feature vector.

Coordinates are corrected for aspect ratio, centred on the shoulder midpoint
and scaled by shoulder width, so features do not depend on where the signer
sits or how far they are from the camera. Hand shape is expressed relative to
the wrist and hand size. Missing parts become zeros with a presence flag.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vsl_features.frames import FloatArray, Frame
from vsl_features.spec import (
    FACE_NOSE_TIP_POSITION,
    FEATURE_SPEC,
    HAND_MIDDLE_MCP,
    HAND_WRIST,
    POSE_LEFT_SHOULDER,
    POSE_RIGHT_SHOULDER,
    POSE_UPPER_BODY,
    FeatureSpec,
)

MIN_SHOULDER_VISIBILITY = 0.5
MIN_SHOULDER_WIDTH = 1e-3


@dataclass(frozen=True)
class BodyFrame:
    """Shoulder-normalised view of a frame: (x, y) in shoulder widths, y down."""

    center: FloatArray  # (2,) in aspect-corrected image units
    scale: float
    left_wrist: FloatArray | None
    right_wrist: FloatArray | None


def _corrected(points: FloatArray, aspect: float) -> FloatArray:
    out = points[:, :2].copy()
    out[:, 0] *= aspect
    return out


def body_frame(frame: Frame, aspect: float) -> BodyFrame | None:
    """Return the shoulder reference, or None if the shoulders are not reliable."""
    if frame.pose is None:
        return None
    pose = frame.pose
    if min(pose[POSE_LEFT_SHOULDER, 3], pose[POSE_RIGHT_SHOULDER, 3]) < MIN_SHOULDER_VISIBILITY:
        return None
    shoulders = _corrected(pose[[POSE_LEFT_SHOULDER, POSE_RIGHT_SHOULDER]], aspect)
    scale = float(np.linalg.norm(shoulders[0] - shoulders[1]))
    if scale < MIN_SHOULDER_WIDTH:
        return None
    center = shoulders.mean(axis=0)

    def wrist(hand: FloatArray | None) -> FloatArray | None:
        if hand is None:
            return None
        result: FloatArray = (_corrected(hand[[HAND_WRIST]], aspect)[0] - center) / scale
        return result

    return BodyFrame(center, scale, wrist(frame.left_hand), wrist(frame.right_hand))


def _hand_features(
    hand: FloatArray | None, body: BodyFrame, aspect: float, n_points: int
) -> FloatArray:
    out = np.zeros(2 + n_points * 3 + 1, dtype=np.float32)
    if hand is None:
        return out
    pts = hand.copy()
    pts[:, 0] *= aspect
    wrist = pts[HAND_WRIST]
    size = float(np.linalg.norm(pts[HAND_MIDDLE_MCP, :2] - wrist[:2])) or body.scale * 0.3
    out[:2] = (wrist[:2] - body.center) / body.scale
    out[2:-1] = ((pts - wrist) / size).reshape(-1)
    out[-1] = 1.0
    return out


def frame_features(
    frame: Frame, aspect: float, spec: FeatureSpec = FEATURE_SPEC
) -> FloatArray | None:
    """Feature vector of length `spec.feature_dim`, or None without reliable shoulders."""
    body = body_frame(frame, aspect)
    if body is None or frame.pose is None:
        return None
    pose = (_corrected(frame.pose[list(POSE_UPPER_BODY)], aspect) - body.center) / body.scale
    face = np.zeros(len(spec.face_indices) * 2 + 1, dtype=np.float32)
    if frame.face is not None:
        f = _corrected(frame.face, aspect)
        face[:-1] = ((f - f[FACE_NOSE_TIP_POSITION]) / body.scale).reshape(-1)
        face[-1] = 1.0
    n_hand = spec.hand_shape[0]
    vector = np.concatenate(
        [
            pose.reshape(-1),
            _hand_features(frame.left_hand, body, aspect, n_hand),
            _hand_features(frame.right_hand, body, aspect, n_hand),
            face,
        ]
    ).astype(np.float32)
    assert vector.shape == (spec.feature_dim,)
    return vector


def sequence_features(frames: list[Frame], aspect: float) -> FloatArray:
    """Stack usable frames into (n, feature_dim); frames without shoulders are skipped."""
    rows = [v for f in frames if (v := frame_features(f, aspect)) is not None]
    if not rows:
        return np.zeros((0, FEATURE_SPEC.feature_dim), dtype=np.float32)
    return np.stack(rows)
