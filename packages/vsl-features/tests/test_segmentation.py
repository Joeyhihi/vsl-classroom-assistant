from __future__ import annotations

import numpy as np
import pytest

from vsl_features.frames import Frame
from vsl_features.segmentation import SegmenterConfig, Utterance, UtteranceSegmenter
from vsl_features.synth import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    Variation,
    synth_rest,
    synth_session,
    synth_sign,
)

ASPECT = IMAGE_WIDTH / IMAGE_HEIGHT


def run(frames: list[Frame], config: SegmenterConfig | None = None) -> list[Utterance]:
    seg = UtteranceSegmenter(ASPECT, config)
    return [u for f in frames if (u := seg.push(f)) is not None]


@pytest.mark.parametrize("fps", [10.0, 15.0, 30.0])
def test_one_utterance_per_sign_at_any_fps(fps: float) -> None:
    frames, truth = synth_session(["SYN_A", "SYN_B", "SYN_C"], fps=fps, seed=3)

    utterances = run(frames)

    assert len(utterances) == 3
    for u, (_, start, end) in zip(utterances, truth, strict=True):
        assert abs(u.start_ms - start) < 350
        assert abs(u.end_ms - end) < 350
        assert u.reason == "rest"
        assert 500 <= u.hysteresis_ms <= 800


def test_rest_only_produces_nothing_and_reports_state() -> None:
    seg = UtteranceSegmenter(ASPECT)
    for f in synth_rest(0, 3000, 15, np.random.default_rng(0)):
        assert seg.push(f) is None
    state_after_rest = seg.state
    seg.push(Frame(5000, None, None, None, None))
    assert (state_after_rest, seg.state) == ("ready", "waiting_for_hands")


def test_short_pause_inside_a_unit_is_tolerated() -> None:
    rng = np.random.default_rng(4)
    sign = synth_sign("SYN_A", 1000, 15, rng)
    # Tracking drops the hands for ~330 ms in the middle of the unit.
    middle = len(sign) // 2
    sign[middle : middle + 5] = [
        Frame(f.t_ms, f.pose, None, None, f.face) for f in sign[middle : middle + 5]
    ]
    frames = synth_rest(0, 1000, 15, rng) + sign + synth_rest(sign[-1].t_ms + 66.7, 1200, 15, rng)

    assert len(run(frames)) == 1


def test_pause_longer_than_tolerance_splits_the_unit() -> None:
    rng = np.random.default_rng(4)
    sign = synth_sign("SYN_A", 1000, 15, rng, Variation(speed=0.6))  # ~2 s pattern
    # ~730 ms without hands (> 600 ms tolerance), with plenty of sign left afterwards.
    sign[12:23] = [Frame(f.t_ms, f.pose, None, None, f.face) for f in sign[12:23]]
    frames = synth_rest(0, 1000, 15, rng) + sign + synth_rest(sign[-1].t_ms + 66.7, 1200, 15, rng)

    assert len(run(frames)) == 2


def test_blips_shorter_than_min_duration_are_discarded() -> None:
    frames, _ = synth_session(["SYN_A"], seed=5)
    assert run(frames, SegmenterConfig(min_duration_ms=10_000)) == []


def test_max_duration_forces_close() -> None:
    frames, _ = synth_session(["SYN_A"], seed=6)
    utterances = run(frames, SegmenterConfig(max_duration_ms=800))
    assert utterances and utterances[0].reason == "max_duration"


def test_trailing_rest_frames_are_excluded() -> None:
    frames, truth = synth_session(["SYN_B"], seed=7)
    (u,) = run(frames)
    assert u.frames[-1].t_ms == u.end_ms <= truth[0][2] + 1


def test_still_hold_ends_at_the_last_moving_frame() -> None:
    """Hands resting ABOVE the rest line (e.g. on a desk in a laptop webcam view)."""
    rng = np.random.default_rng(8)
    sign = synth_sign("SYN_A", 1000, 15, rng)
    pattern = sign[: len(sign) - 6]  # stop before the hands are lowered
    last = pattern[-1]
    hold = [
        Frame(last.t_ms + 66.7 * (i + 1), last.pose, last.left_hand, last.right_hand, last.face)
        for i in range(40)  # ~2.7 s motionless, hands up
    ]
    (u,) = run(synth_rest(0, 1000, 15, rng) + pattern + hold)

    assert u.reason == "still"
    assert u.end_ms <= last.t_ms  # the motionless hold is not part of the unit
    assert 1400 <= u.hysteresis_ms <= 1700  # the wait is reported, not 0
