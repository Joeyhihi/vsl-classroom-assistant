"""Assign detected hands to the signer's left/right (mirrors handAssigner.ts).

MediaPipe's per-hand left/right label flips under motion blur, so hands are
matched to the pose wrists (pose 15 = left, 16 = right, anatomical), then to the
previous frame's hand positions, and only then to the model's label. Stateful:
use one assigner per stream.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

POSE_LEFT_WRIST = 15
POSE_RIGHT_WRIST = 16
MIN_WRIST_VISIBILITY = 0.3
MAX_STALE_FRAMES = 5

Side = Literal["left", "right"]
Array = NDArray[np.float32]


@dataclass(frozen=True)
class DetectedHand:
    landmarks: Array  # (21, 3), normalised image coordinates
    label: str | None = None  # "Left" / "Right" as reported by the model


def _label_side(label: str | None) -> Side | None:
    # Verified on Windows (P3): on unmirrored frames the label names the signer's hand.
    if label == "Left":
        return "left"
    if label == "Right":
        return "right"
    return None


def _dist(a: Array, b: Array) -> float:
    return float(np.hypot(*(a[:2] - b[:2])))


class HandAssigner:
    def __init__(self) -> None:
        self._prev: dict[Side, Array | None] = {"left": None, "right": None}
        self._stale: dict[Side, int] = {"left": 0, "right": 0}

    def _anchors(self, pose: Array | None) -> dict[Side, Array | None]:
        def wrist(i: int) -> Array | None:
            if pose is None or pose.shape[0] <= i:
                return None
            visible = pose.shape[1] < 4 or pose[i, 3] >= MIN_WRIST_VISIBILITY
            return pose[i] if visible else None

        left, right = wrist(POSE_LEFT_WRIST), wrist(POSE_RIGHT_WRIST)
        return {
            "left": left if left is not None else self._prev["left"],
            "right": right if right is not None else self._prev["right"],
        }

    def assign(
        self, hands: Sequence[DetectedHand], pose: Array | None
    ) -> tuple[Array | None, Array | None]:
        """Returns (left, right)."""
        anchors = self._anchors(pose)
        left_anchor, right_anchor = anchors["left"], anchors["right"]
        left: Array | None = None
        right: Array | None = None

        if len(hands) >= 2:
            a, b = hands[0], hands[1]
            wa, wb = a.landmarks[0], b.landmarks[0]
            if left_anchor is not None and right_anchor is not None:
                keep = _dist(wa, left_anchor) + _dist(wb, right_anchor)
                swap = _dist(wa, right_anchor) + _dist(wb, left_anchor)
                a_is_left = keep <= swap
            else:
                sa, sb = _label_side(a.label), _label_side(b.label)
                # Unmirrored frame: the signer's left hand is on the image's right.
                a_is_left = sa == "left" if sa and sb and sa != sb else bool(wa[0] > wb[0])
            left, right = (a.landmarks, b.landmarks) if a_is_left else (b.landmarks, a.landmarks)
        elif len(hands) == 1:
            hand = hands[0]
            wrist = hand.landmarks[0]
            side: Side | None = None
            if left_anchor is not None and right_anchor is not None:
                side = (
                    "left" if _dist(wrist, left_anchor) <= _dist(wrist, right_anchor) else "right"
                )
            elif left_anchor is not None:
                side = "left"
            elif right_anchor is not None:
                side = "right"
            side = side or _label_side(hand.label) or ("left" if wrist[0] > 0.5 else "right")
            if side == "left":
                left = hand.landmarks
            else:
                right = hand.landmarks

        self._remember("left", left)
        self._remember("right", right)
        return left, right

    def _remember(self, side: Side, hand: Array | None) -> None:
        if hand is not None:
            self._prev[side] = hand[0]
            self._stale[side] = 0
        else:
            self._stale[side] += 1
            if self._stale[side] > MAX_STALE_FRAMES:
                self._prev[side] = None
