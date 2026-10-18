"""Training-time augmentation on normalised feature sequences (fs-1 layout).

Speed change and frame drops resample whole frames (nearest index), so the
presence flags stay 0/1. Gaussian noise is added only to parts that are present.
Mirroring is not done here: it needs expert approval per item (`mirroring_ok`, B1).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from vsl_features.spec import FEATURE_SPEC, POSE_UPPER_BODY, FeatureSpec

FloatArray = NDArray[np.float32]


def part_slices(spec: FeatureSpec = FEATURE_SPEC) -> dict[str, slice]:
    """Column ranges of each part in `normalize.frame_features` (the flag is the last column)."""
    pose = len(POSE_UPPER_BODY) * 2
    hand = 2 + spec.hand_shape[0] * 3 + 1
    return {
        "pose": slice(0, pose),
        "left_hand": slice(pose, pose + hand),
        "right_hand": slice(pose + hand, pose + 2 * hand),
        "face": slice(pose + 2 * hand, spec.feature_dim),
    }


def presence_columns(spec: FeatureSpec = FEATURE_SPEC) -> tuple[int, ...]:
    slices = part_slices(spec)
    return tuple(slices[p].stop - 1 for p in ("left_hand", "right_hand", "face"))


def augment(
    seq: FloatArray,
    rng: np.random.Generator,
    *,
    speed: tuple[float, float] = (0.8, 1.25),
    drop: float = 0.1,
    noise: float = 0.02,
) -> FloatArray:
    n = len(seq)
    if n < 2:
        return seq.copy()
    factor = rng.uniform(*speed)
    length = max(2, round(n / factor))
    out = seq[np.round(np.linspace(0, n - 1, length)).astype(int)]
    if drop > 0 and len(out) > 4:
        keep = rng.random(len(out)) >= drop
        keep[0] = keep[-1] = True
        out = out[keep]
    out = out.copy()
    if noise > 0:
        slices = part_slices()
        pose = slices["pose"]
        out[:, pose] += rng.normal(0.0, noise, (len(out), pose.stop - pose.start))
        for part in ("left_hand", "right_hand", "face"):
            s = slices[part]
            present = out[:, s.stop - 1 : s.stop]
            out[:, s.start : s.stop - 1] += (
                rng.normal(0.0, noise, (len(out), s.stop - 1 - s.start)) * present
            )
    result: FloatArray = out.astype(np.float32)
    return result
