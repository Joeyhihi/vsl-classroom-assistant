from __future__ import annotations

import math

import numpy as np
import pytest

from vsl_features.decoding import CooldownFilter, DecisionPolicy, softmax
from vsl_features.dtw import dtw_distance


def wave(n: int, freq: float) -> np.ndarray:
    t = np.linspace(0, 1, n)
    return np.stack(
        [np.sin(2 * math.pi * freq * t), np.cos(2 * math.pi * freq * t)], axis=1
    ).astype(np.float32)


def test_dtw_identical_is_zero_and_symmetric() -> None:
    a, b = wave(30, 1), wave(40, 2)
    assert dtw_distance(a, a) == pytest.approx(0.0)
    assert dtw_distance(a, b) == pytest.approx(dtw_distance(b, a), rel=1e-6)


def test_dtw_tolerates_tempo_but_not_shape() -> None:
    slow, fast, other = wave(45, 1), wave(30, 1), wave(30, 2)
    assert dtw_distance(slow, fast) < 0.2 * dtw_distance(fast, other)


def test_dtw_empty_is_infinite() -> None:
    assert math.isinf(dtw_distance(np.zeros((0, 2), np.float32), wave(5, 1)))


def test_softmax_sums_to_one_and_temperature_sharpens() -> None:
    soft = softmax([1.0, 0.0], temperature=1.0)
    sharp = softmax([1.0, 0.0], temperature=0.1)
    assert sum(soft) == pytest.approx(1.0)
    assert sharp[0] > soft[0]


@pytest.mark.parametrize(
    ("ranked", "expected"),
    [
        ([("A", 0.9), ("B", 0.05)], "confident"),
        ([("A", 0.75), ("B", 0.6)], "uncertain"),  # margin too small
        ([("A", 0.5), ("B", 0.3)], "uncertain"),  # below threshold
        ([("A", 0.3), ("B", 0.2)], "rejected"),  # below floor
        ([("__distractor__", 0.95), ("A", 0.01)], "rejected"),
        ([], "rejected"),
    ],
)
def test_policy(ranked: list[tuple[str, float]], expected: str) -> None:
    assert DecisionPolicy().decide(ranked) == expected


def test_cooldown_suppresses_repeats_within_window() -> None:
    f = CooldownFilter(window_ms=1500)
    assert f.allow("A", 0)
    assert not f.allow("A", 1000)
    assert f.allow("B", 1100)
    assert f.allow("A", 1200)
    assert f.allow("A", 2800)
