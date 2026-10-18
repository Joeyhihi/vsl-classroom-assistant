"""Frame validation: untrusted wire data → typed arrays.

Invalid frames raise `FrameError`; callers drop and count them rather than
ending the session (docs/API_CONTRACTS.md).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from vsl_features.spec import FEATURE_SPEC, FeatureSpec

FloatArray = NDArray[np.float32]

XY_RANGE = (-0.5, 1.5)
Z_RANGE = (-5.0, 5.0)
VISIBILITY_RANGE = (0.0, 1.0)


class FrameError(ValueError):
    """A frame that must be dropped; the message is safe to log (no values)."""


@dataclass(frozen=True)
class Frame:
    t_ms: float
    pose: FloatArray | None
    left_hand: FloatArray | None  # signer's anatomical left
    right_hand: FloatArray | None
    face: FloatArray | None

    @property
    def hands_visible(self) -> bool:
        return self.left_hand is not None or self.right_hand is not None


def _array(raw: Any, shape: tuple[int, int], name: str) -> FloatArray | None:
    if raw is None:
        return None
    try:
        arr = np.asarray(raw, dtype=np.float32)
    except (TypeError, ValueError):
        raise FrameError(f"{name}: not numeric") from None
    if arr.shape != shape:
        raise FrameError(f"{name}: expected shape {shape}, got {arr.shape}")
    if not np.all(np.isfinite(arr)):
        raise FrameError(f"{name}: non-finite value")
    xy, z = arr[:, :2], arr[:, 2]
    if xy.min() < XY_RANGE[0] or xy.max() > XY_RANGE[1]:
        raise FrameError(f"{name}: x/y out of range")
    if z.min() < Z_RANGE[0] or z.max() > Z_RANGE[1]:
        raise FrameError(f"{name}: z out of range")
    if shape[1] == 4:
        vis = arr[:, 3]
        if vis.min() < VISIBILITY_RANGE[0] or vis.max() > VISIBILITY_RANGE[1]:
            raise FrameError(f"{name}: visibility out of range")
    return arr


def parse_frame(raw: Mapping[str, Any], spec: FeatureSpec = FEATURE_SPEC) -> Frame:
    t = raw.get("t_ms")
    if isinstance(t, bool) or not isinstance(t, int | float) or not np.isfinite(t) or t < 0:
        raise FrameError("t_ms: invalid")
    return Frame(
        t_ms=float(t),
        pose=_array(raw.get("pose"), spec.pose_shape, "pose"),
        left_hand=_array(raw.get("left_hand"), spec.hand_shape, "left_hand"),
        right_hand=_array(raw.get("right_hand"), spec.hand_shape, "right_hand"),
        face=_array(raw.get("face"), spec.face_shape, "face"),
    )


def frame_to_wire(frame: Frame, decimals: int = 4) -> dict[str, Any]:
    def arr(a: FloatArray | None) -> list[list[float]] | None:
        return None if a is None else np.round(a.astype(np.float64), decimals).tolist()

    return {
        "t_ms": round(frame.t_ms, 1),
        "pose": arr(frame.pose),
        "left_hand": arr(frame.left_hand),
        "right_hand": arr(frame.right_hand),
        "face": arr(frame.face),
    }
