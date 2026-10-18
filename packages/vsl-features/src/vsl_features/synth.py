"""Deterministic synthetic signer (no real person; safe for the public repo).

Three made-up motion patterns stand in for signs so the pipeline (segmenter,
normalisation, template classifier, WS protocol, replay UI) can be tested on
the M1 Mac without a camera or MediaPipe. They are NOT VSL signs.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from vsl_features.frames import Frame
from vsl_features.spec import FEATURE_SPEC

IMAGE_WIDTH, IMAGE_HEIGHT = 640, 480

SYNTHETIC_LABELS: dict[str, tuple[str, str]] = {
    # gloss_id: (text_vi, icon)
    "SYN_A": ("Mẫu tổng hợp A (vòng tròn)", "circle"),
    "SYN_B": ("Mẫu tổng hợp B (vẫy)", "wave"),
    "SYN_C": ("Mẫu tổng hợp C (đẩy)", "push"),
}

_SHOULDER_Y = 0.45
# Laptop-webcam framing, matched to the developer's real L2 takes (P4): resting
# hands visible at the bottom ~0.8 shoulder widths below the shoulders, signing in
# front of the chest/face (<= ~0.2 below the shoulders).
_REST_RIGHT = np.array([0.40, 0.66])
_REST_LEFT = np.array([0.60, 0.66])
_HAND_SIZE = 0.06


@dataclass(frozen=True)
class Variation:
    speed: float = 1.0
    amplitude: float = 1.0
    offset: tuple[float, float] = (0.0, 0.0)
    noise: float = 0.002

    @staticmethod
    def random(rng: np.random.Generator) -> Variation:
        return Variation(
            speed=float(rng.uniform(0.85, 1.15)),
            amplitude=float(rng.uniform(0.9, 1.1)),
            offset=(float(rng.uniform(-0.01, 0.01)), float(rng.uniform(-0.01, 0.01))),
        )


def _hand_shape(spread: float, curl: float) -> np.ndarray:
    """21 hand points relative to the wrist (image units), MediaPipe ordering."""
    pts = [np.zeros(2)]
    for finger in range(5):
        angle = math.radians(-60 + finger * 30 * spread) - math.pi / 2
        for joint in range(1, 5):
            reach = joint * 0.25 * (1.0 - curl * (joint - 1) / 4)
            pts.append(np.array([math.cos(angle), math.sin(angle)]) * reach)
    return np.stack(pts) * _HAND_SIZE


_SHAPES = {
    "open": _hand_shape(1.2, 0.0),
    "spread": _hand_shape(1.6, 0.1),
    "fist": _hand_shape(0.6, 0.9),
}

Path = Callable[[float, Variation], np.ndarray]  # phase 0..1 → wrist (x, y)

_SIGNS: dict[str, tuple[Path, str]] = {
    "SYN_A": (
        lambda p, v: (
            np.array([0.42, 0.40])
            + 0.07 * v.amplitude * np.array([math.cos(2 * math.pi * p), math.sin(2 * math.pi * p)])
        ),
        "open",
    ),
    "SYN_B": (
        lambda p, v: np.array([0.38 + 0.08 * v.amplitude * math.sin(4 * math.pi * p), 0.34]),
        "spread",
    ),
    "SYN_C": (
        lambda p, v: np.array([0.45, 0.50 - 0.18 * v.amplitude * math.sin(math.pi * p)]),
        "fist",
    ),
}

_SIGN_MS = 1200.0
_TRANSITION_MS = 300.0


def _frame(
    t_ms: float,
    right_wrist: np.ndarray,
    right_shape: np.ndarray,
    left_visible: bool,
    rng: np.random.Generator,
    noise: float,
) -> Frame:
    def jitter(a: np.ndarray) -> np.ndarray:
        return a + rng.normal(0.0, noise, a.shape)

    pose = np.zeros(FEATURE_SPEC.pose_shape, dtype=np.float32)
    pose[:, 3] = 0.99
    anchors = {
        0: (0.50, 0.25), 11: (0.60, _SHOULDER_Y), 12: (0.40, _SHOULDER_Y),
        13: (0.64, 0.66), 23: (0.57, 0.85), 24: (0.43, 0.85),
    }  # fmt: skip
    for i in range(33):
        pose[i, :2] = anchors.get(i, (0.5, 0.6))
    pose[15, :2] = _REST_LEFT
    pose[16, :2] = right_wrist
    pose[14, :2] = (np.array([0.40, _SHOULDER_Y]) + right_wrist) / 2 + np.array([-0.04, 0.0])
    pose[:, :2] = jitter(pose[:, :2])

    def hand(wrist: np.ndarray, shape: np.ndarray) -> np.ndarray:
        h = np.zeros(FEATURE_SPEC.hand_shape, dtype=np.float32)
        h[:, :2] = jitter(wrist + shape)
        h[:, 2] = jitter(np.linspace(0.0, -0.05, 21))
        return h

    face = np.zeros(FEATURE_SPEC.face_shape, dtype=np.float32)
    n = len(FEATURE_SPEC.face_indices)
    angles = np.linspace(0, 2 * math.pi, n, endpoint=False)
    face[:, 0] = 0.5 + 0.05 * np.cos(angles)
    face[:, 1] = 0.25 + 0.06 * np.sin(angles)
    face[:, :2] = jitter(face[:, :2])

    return Frame(
        t_ms=round(t_ms, 1),
        pose=pose,
        left_hand=hand(_REST_LEFT, _SHAPES["open"]) if left_visible else None,
        right_hand=hand(right_wrist, right_shape),
        face=face,
    )


def synth_rest(
    start_ms: float, duration_ms: float, fps: float, rng: np.random.Generator
) -> list[Frame]:
    step = 1000.0 / fps
    count = int(duration_ms / step)
    return [
        _frame(start_ms + i * step, _REST_RIGHT, _SHAPES["open"], i % 2 == 0, rng, 0.002)
        for i in range(count)
    ]


def synth_sign(
    label: str,
    start_ms: float,
    fps: float,
    rng: np.random.Generator,
    variation: Variation | None = None,
) -> list[Frame]:
    """Raise → pattern → lower. Returns frames starting at `start_ms`."""
    v = variation or Variation()
    path, shape_name = _SIGNS[label]
    shape = _SHAPES[shape_name]
    step = 1000.0 / fps
    sign_ms = _SIGN_MS / v.speed
    total = 2 * _TRANSITION_MS + sign_ms
    offset = np.array(v.offset)
    start_pos, end_pos = path(0.0, v) + offset, path(1.0, v) + offset
    frames = []
    for i in range(int(total / step)):
        t = i * step
        if t < _TRANSITION_MS:
            a = t / _TRANSITION_MS
            wrist = (1 - a) * _REST_RIGHT + a * start_pos
        elif t < _TRANSITION_MS + sign_ms:
            wrist = path((t - _TRANSITION_MS) / sign_ms, v) + offset
        else:
            a = (t - _TRANSITION_MS - sign_ms) / _TRANSITION_MS
            wrist = (1 - a) * end_pos + a * _REST_RIGHT
        frames.append(_frame(start_ms + t, wrist, shape, True, rng, v.noise))
    return frames


def synth_session(
    labels: list[str], fps: float = 15.0, seed: int = 0, rest_ms: float = 1000.0
) -> tuple[list[Frame], list[tuple[str, float, float]]]:
    """Rest, sign, rest, sign, … rest. Returns frames and (label, start_ms, end_ms) truth."""
    rng = np.random.default_rng(seed)
    frames = synth_rest(0.0, rest_ms, fps, rng)
    truth = []
    for label in labels:
        t0 = frames[-1].t_ms + 1000.0 / fps
        sign = synth_sign(label, t0, fps, rng, Variation.random(rng))
        frames += sign
        truth.append((label, sign[0].t_ms, sign[-1].t_ms))
        frames += synth_rest(frames[-1].t_ms + 1000.0 / fps, rest_ms, fps, rng)
    return frames, truth
