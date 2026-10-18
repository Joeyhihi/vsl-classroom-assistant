from __future__ import annotations

import numpy as np
import pytest

from vsl_features.handedness import DetectedHand, HandAssigner


def hand(x: float, y: float = 0.5) -> np.ndarray:
    h = np.zeros((21, 3), dtype=np.float32)
    h[:, 0], h[:, 1] = x, y
    return h


def pose(left_x: float = 0.7, right_x: float = 0.3, vis: float = 0.9) -> np.ndarray:
    p = np.zeros((33, 4), dtype=np.float32)
    p[:, 3] = vis
    p[15, :2] = (left_x, 0.5)  # signer's left wrist: image right (unmirrored)
    p[16, :2] = (right_x, 0.5)
    return p


@pytest.mark.parametrize("labels", [("Left", "Right"), ("Right", "Left"), (None, None)])
def test_two_hands_follow_pose_wrists_whatever_the_labels(
    labels: tuple[str | None, str | None],
) -> None:
    left, right = HandAssigner().assign(
        [DetectedHand(hand(0.31), labels[0]), DetectedHand(hand(0.69), labels[1])], pose()
    )
    assert left is not None and right is not None
    assert left[0, 0] == pytest.approx(0.69) and right[0, 0] == pytest.approx(0.31)


def test_fast_motion_label_flip_does_not_flicker() -> None:
    assigner = HandAssigner()
    sides = []
    for i, label in enumerate(["Right", "Right", "Left", "Right", "Left"]):  # classifier flicker
        x = 0.3 + i * 0.02  # right hand moving fast near the right wrist
        _left, right = assigner.assign([DetectedHand(hand(x), label)], pose(right_x=x))
        sides.append("right" if right is not None else "left")
    assert sides == ["right"] * 5


def test_previous_positions_bridge_frames_without_visible_wrists() -> None:
    assigner = HandAssigner()
    assigner.assign([DetectedHand(hand(0.3))], pose())
    hidden = pose(vis=0.0)  # wrists not visible (e.g. motion blur)
    left, right = assigner.assign([DetectedHand(hand(0.33), "Left")], hidden)
    assert right is not None and left is None


def test_labels_are_the_last_resort_and_name_the_signers_hand() -> None:
    left, right = HandAssigner().assign([DetectedHand(hand(0.5), "Left")], None)
    assert left is not None and right is None


def test_no_hands() -> None:
    assert HandAssigner().assign([], pose()) == (None, None)
