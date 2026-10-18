from __future__ import annotations

import numpy as np

from vsl_features.frames import Frame
from vsl_features.normalize import frame_features, sequence_features
from vsl_features.spec import FEATURE_SPEC
from vsl_features.synth import IMAGE_HEIGHT, IMAGE_WIDTH, synth_session

ASPECT = IMAGE_WIDTH / IMAGE_HEIGHT


def sample() -> Frame:
    frames, _ = synth_session(["SYN_B"], seed=2)
    return frames[25]


def transformed(frame: Frame, scale: float, shift: tuple[float, float]) -> Frame:
    def tf(a: np.ndarray | None) -> np.ndarray | None:
        if a is None:
            return None
        out = a.copy()
        out[:, 0] = (out[:, 0] - 0.5) * scale + 0.5 + shift[0]
        out[:, 1] = (out[:, 1] - 0.5) * scale + 0.5 + shift[1]
        out[:, 2] *= scale  # MediaPipe z uses roughly the same scale as x
        return out

    return Frame(
        frame.t_ms, tf(frame.pose), tf(frame.left_hand), tf(frame.right_hand), tf(frame.face)
    )


def test_feature_vector_length() -> None:
    v = frame_features(sample(), ASPECT)
    assert v is not None and v.shape == (FEATURE_SPEC.feature_dim,) and v.dtype == np.float32


def test_invariant_to_position_and_distance() -> None:
    base = sample()
    v0 = frame_features(base, ASPECT)
    v1 = frame_features(transformed(base, scale=0.7, shift=(0.08, -0.05)), ASPECT)
    assert v0 is not None and v1 is not None
    np.testing.assert_allclose(v0, v1, atol=1e-4)


def test_unreliable_shoulders_give_none() -> None:
    base = sample()
    assert base.pose is not None
    pose = base.pose.copy()
    pose[11, 3] = 0.1
    assert frame_features(Frame(base.t_ms, pose, None, None, None), ASPECT) is None
    assert frame_features(Frame(base.t_ms, None, None, None, None), ASPECT) is None


def test_missing_hand_is_zero_with_presence_flag() -> None:
    base = sample()
    v = frame_features(Frame(base.t_ms, base.pose, None, base.right_hand, None), ASPECT)
    assert v is not None
    pose_len = 9 * 2
    hand_len = 2 + 21 * 3 + 1
    left = v[pose_len : pose_len + hand_len]
    right = v[pose_len + hand_len : pose_len + 2 * hand_len]
    assert not left.any()
    assert right[-1] == 1.0
    assert v[-1] == 0.0  # face presence


def test_sequence_skips_unusable_frames() -> None:
    base = sample()
    no_pose = Frame(base.t_ms + 1, None, None, None, None)
    assert sequence_features([base, no_pose, base], ASPECT).shape == (2, FEATURE_SPEC.feature_dim)
    assert sequence_features([no_pose], ASPECT).shape == (0, FEATURE_SPEC.feature_dim)
