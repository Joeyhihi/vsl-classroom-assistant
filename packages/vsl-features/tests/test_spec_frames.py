from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from vsl_features.frames import FrameError, frame_to_wire, parse_frame
from vsl_features.spec import FEATURE_SPEC
from vsl_features.synth import synth_session


def wire_frame() -> dict[str, Any]:
    frames, _ = synth_session(["SYN_A"], seed=1)
    return frame_to_wire(frames[20])


def test_spec_wire_shapes() -> None:
    wire = FEATURE_SPEC.to_wire()
    assert wire["version"] == "fs-1"
    assert wire["shapes"] == {"pose": [33, 4], "hand": [21, 3], "face": [40, 3]}
    assert len(wire["face_indices"]) == 40 == len(set(wire["face_indices"]))


def test_roundtrip_through_wire() -> None:
    raw = wire_frame()
    frame = parse_frame(raw)
    assert frame.pose is not None and frame.pose.shape == (33, 4)
    assert frame_to_wire(frame) == raw


def test_missing_parts_are_none() -> None:
    raw = wire_frame() | {"left_hand": None, "face": None}
    frame = parse_frame(raw)
    assert frame.left_hand is None and frame.face is None


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"t_ms": -1}, "t_ms"),
        ({"t_ms": True}, "t_ms"),
        ({"t_ms": "12"}, "t_ms"),
        ({"right_hand": [[0.1, 0.1, 0.0]] * 20}, "shape"),
        ({"pose": "nope"}, "pose"),
    ],
)
def test_invalid_frames_raise(patch: dict[str, Any], message: str) -> None:
    with pytest.raises(FrameError, match=message):
        parse_frame(wire_frame() | patch)


@pytest.mark.parametrize(
    ("index", "value", "message"),
    [(0, float("nan"), "non-finite"), (0, 3.0, "x/y out of range"), (2, 9.0, "z out of range")],
)
def test_value_checks(index: int, value: float, message: str) -> None:
    raw = wire_frame()
    hand = np.asarray(raw["right_hand"])
    hand[0, index] = value
    with pytest.raises(FrameError, match=message):
        parse_frame(raw | {"right_hand": hand.tolist()})


def test_error_messages_do_not_contain_values() -> None:
    raw = wire_frame()
    hand = np.asarray(raw["right_hand"])
    hand[3, 0] = 1.2345678
    hand[3, 1] = 7.654321
    with pytest.raises(FrameError) as info:
        parse_frame(raw | {"right_hand": hand.tolist()})
    assert "7.65" not in str(info.value)
