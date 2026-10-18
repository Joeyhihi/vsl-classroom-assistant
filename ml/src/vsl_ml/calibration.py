"""Temperature scaling and the operating point (docs/AI_ML_STRATEGY.md §2 step 7, §4).

The operating point favours precision: a wrong word spoken aloud costs more
than "please sign again". It is chosen on validation data only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from vsl_features.decoding import REJECTION_LABELS, DecisionPolicy

THRESHOLDS = tuple(round(t, 2) for t in np.arange(0.40, 0.96, 0.05))
MARGINS = (0.1, 0.2, 0.3)
FLOOR = 0.35


def softmax_rows(
    logits: NDArray[np.floating[Any]], temperature: float = 1.0
) -> NDArray[np.float64]:
    z = np.asarray(logits, dtype=np.float64) / max(temperature, 1e-6)
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    result: NDArray[np.float64] = e / e.sum(axis=1, keepdims=True)
    return result


def nll(logits: NDArray[np.floating[Any]], y: NDArray[np.int64], temperature: float) -> float:
    p = softmax_rows(logits, temperature)[np.arange(len(y)), y]
    return float(-np.log(np.clip(p, 1e-12, None)).mean())


def fit_temperature(logits: NDArray[np.floating[Any]], y: NDArray[np.int64]) -> float:
    """Grid search over log(T), then a finer grid around the best value."""
    if len(y) == 0:
        return 1.0
    grid = np.exp(np.linspace(np.log(0.02), np.log(50.0), 200))
    best = min(grid, key=lambda t: nll(logits, y, float(t)))
    fine = np.exp(np.linspace(np.log(best) - 0.05, np.log(best) + 0.05, 41))
    return float(min(fine, key=lambda t: nll(logits, y, float(t))))


def statuses(
    probs: NDArray[np.float64], class_names: list[str], policy: DecisionPolicy
) -> tuple[list[str], NDArray[np.int64]]:
    """Per-sample decision status and predicted class index (one decision per utterance)."""
    out: list[str] = []
    preds = probs.argmax(axis=1)
    for row in probs:
        order = np.argsort(-row)[:3]
        out.append(policy.decide([(class_names[i], float(row[i])) for i in order]))
    return out, preds.astype(np.int64)


@dataclass(frozen=True)
class OperatingPoint:
    threshold: float
    margin: float
    floor: float
    far: float  # non-target samples accepted as a confident sign
    wrong_rate: float  # target samples confidently given the wrong sign
    coverage: float  # target samples confidently given the right sign
    meets_target: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def rates(
    probs: NDArray[np.float64],
    y: NDArray[np.int64],
    class_names: list[str],
    policy: DecisionPolicy,
) -> tuple[float, float, float]:
    """(FAR on non-targets, confident-wrong rate on targets, coverage on targets)."""
    status, preds = statuses(probs, class_names, policy)
    is_target = np.array([class_names[i] not in REJECTION_LABELS for i in y], dtype=bool)
    confident = np.array([s == "confident" for s in status], dtype=bool)
    correct = preds == y
    far = float(confident[~is_target].mean()) if (~is_target).any() else 0.0
    if is_target.any():
        wrong = float((confident & ~correct)[is_target].mean())
        coverage = float((confident & correct)[is_target].mean())
    else:
        wrong = coverage = 0.0
    return far, wrong, coverage


def choose_operating_point(
    probs: NDArray[np.float64],
    y: NDArray[np.int64],
    class_names: list[str],
    max_far: float = 0.05,
) -> OperatingPoint:
    """Most coverage with FAR and confident-wrong rate both ≤ `max_far`.

    If no point meets the target, the safest point (lowest FAR + wrong rate) is
    returned with `meets_target=False`; the G5 review decides what to do.
    """
    points = []
    for threshold in THRESHOLDS:
        for margin in MARGINS:
            floor = min(FLOOR, threshold)
            far, wrong, coverage = rates(
                probs, y, class_names, DecisionPolicy(threshold, margin, floor)
            )
            ok = far <= max_far and wrong <= max_far
            points.append(OperatingPoint(threshold, margin, floor, far, wrong, coverage, ok))
    feasible = [p for p in points if p.meets_target]
    if feasible:
        return max(feasible, key=lambda p: (p.coverage, p.threshold, p.margin))
    return min(points, key=lambda p: (p.far + p.wrong_rate, -p.coverage, -p.threshold))
