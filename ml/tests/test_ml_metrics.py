from __future__ import annotations

import numpy as np

from vsl_features.decoding import DecisionPolicy
from vsl_ml.augment import augment, part_slices, presence_columns
from vsl_ml.calibration import choose_operating_point, fit_temperature, nll, softmax_rows
from vsl_ml.metrics import evaluate, expected_calibration_error

CLASSES = ["A", "B", "__background__"]


def test_temperature_softens_overconfident_logits() -> None:
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 400)
    sharp = (np.eye(3)[y] * 2.0 + rng.normal(0, 1.0, (400, 3))) * 5.0
    t = fit_temperature(sharp, y)

    assert t > 2.0
    assert nll(sharp, y, t) < nll(sharp, y, 1.0)
    assert fit_temperature(np.zeros((0, 3)), np.zeros(0, dtype=np.int64)) == 1.0


def test_operating_point_rejects_background() -> None:
    # Background takes look like a weak "A": a low threshold would accept them.
    probs = np.array([[0.95, 0.03, 0.02]] * 8 + [[0.04, 0.94, 0.02]] * 8 + [[0.6, 0.1, 0.3]] * 8)
    y = np.array([0] * 8 + [1] * 8 + [2] * 8)
    point = choose_operating_point(probs, y, CLASSES, max_far=0.05)

    assert point.meets_target and point.far == 0.0
    assert point.threshold > 0.6 and point.coverage == 1.0


def test_operating_point_falls_back_to_the_safest() -> None:
    probs = np.array([[0.97, 0.02, 0.01]] * 4)
    y = np.array([2, 2, 0, 0])  # background confidently called "A"
    point = choose_operating_point(probs, y, CLASSES, max_far=0.05)

    assert not point.meets_target


def test_evaluate_counts() -> None:
    probs = softmax_rows(np.array([[5.0, 0, 0], [0, 5.0, 0], [5.0, 0, 0], [0, 0, 5.0]]))
    y = np.array([0, 1, 1, 2])
    ev = evaluate(probs, y, CLASSES, ["S1", "S1", "S2", "S2"], DecisionPolicy(), seed=0)

    assert ev.accuracy == 0.75
    assert ev.per_class["B"]["recall"] == 0.5 and ev.per_class["A"]["precision"] == 0.5
    assert ev.per_signer == {"S1": 1.0, "S2": 0.0} and ev.min_signer_accuracy == 0.0
    assert ev.far == 0.0 and ev.wrong_rate == 1 / 3 and ev.coverage == 2 / 3
    assert ev.confusion == [[1, 0, 0], [1, 1, 0], [0, 0, 1]]
    assert "__background__" not in ev.per_class
    assert ev.macro_f1_ci[0] <= ev.macro_f1 <= ev.macro_f1_ci[1]


def test_ece_is_zero_when_calibrated() -> None:
    probs = np.array([[1.0, 0.0]] * 5)
    assert expected_calibration_error(probs, np.zeros(5, dtype=np.int64)) == 0.0


def test_augment_keeps_flags_binary_and_absent_parts_zero() -> None:
    rng = np.random.default_rng(0)
    seq = rng.normal(size=(30, 231)).astype(np.float32)
    left = part_slices()["left_hand"]
    seq[:, left] = 0.0  # left hand absent
    for col in presence_columns():
        seq[:, col] = 1.0
    seq[:, left.stop - 1] = 0.0

    out = augment(seq, rng)

    assert out.dtype == np.float32 and 2 <= len(out) <= 40
    assert set(np.unique(out[:, list(presence_columns())])) <= {0.0, 1.0}
    assert not out[:, left].any()
