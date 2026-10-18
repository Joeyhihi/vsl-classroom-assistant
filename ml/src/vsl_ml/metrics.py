"""Evaluation metrics (docs/AI_ML_STRATEGY.md §4). NumPy only."""

from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from vsl_features.decoding import REJECTION_LABELS, DecisionPolicy
from vsl_ml.calibration import rates

ECE_BINS = 10
BOOTSTRAP = 500


@dataclass(frozen=True)
class Evaluation:
    n: int
    accuracy: float
    macro_f1: float
    macro_f1_ci: tuple[float, float]
    top3: float
    far: float
    wrong_rate: float
    coverage: float
    ece: float
    min_signer_accuracy: float
    per_class: dict[str, dict[str, float]]
    per_signer: dict[str, float]
    confusion: list[list[int]]
    class_names: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def macro_f1(
    y: NDArray[np.int64], pred: NDArray[np.int64], target_idx: list[int]
) -> tuple[float, dict[int, tuple[float, float, float, int]]]:
    per: dict[int, tuple[float, float, float, int]] = {}
    for k in target_idx:
        tp = int(((pred == k) & (y == k)).sum())
        fp = int(((pred == k) & (y != k)).sum())
        fn = int(((pred != k) & (y == k)).sum())
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        per[k] = (p, r, f, tp + fn)
    present = [v[2] for v in per.values() if v[3] > 0]
    return (float(np.mean(present)) if present else 0.0), per


def expected_calibration_error(probs: NDArray[np.float64], y: NDArray[np.int64]) -> float:
    conf = probs.max(axis=1)
    correct = probs.argmax(axis=1) == y
    edges = np.linspace(0.0, 1.0, ECE_BINS + 1)
    ece = 0.0
    for lo, hi in itertools.pairwise(edges):
        in_bin = (conf > lo) & (conf <= hi)
        if in_bin.any():
            ece += in_bin.mean() * abs(correct[in_bin].mean() - conf[in_bin].mean())
    return float(ece)


def evaluate(
    probs: NDArray[np.float64],
    y: NDArray[np.int64],
    class_names: list[str],
    signers: list[str],
    policy: DecisionPolicy,
    seed: int = 0,
) -> Evaluation:
    if len(y) == 0:
        raise ValueError("nothing to evaluate")
    pred = probs.argmax(axis=1).astype(np.int64)
    target_idx = [i for i, c in enumerate(class_names) if c not in REJECTION_LABELS]
    f1, per = macro_f1(y, pred, target_idx)

    rng = np.random.default_rng(seed)
    boot = [
        macro_f1(y[idx], pred[idx], target_idx)[0]
        for idx in (rng.integers(0, len(y), len(y)) for _ in range(BOOTSTRAP))
    ]
    ci = (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)))

    is_target = np.isin(y, target_idx)
    top3_hits = [y[i] in np.argsort(-probs[i])[:3] for i in np.flatnonzero(is_target)]
    far, wrong, coverage = rates(probs, y, class_names, policy)

    signer_arr = np.array(signers)
    per_signer = {
        s: float((pred == y)[(signer_arr == s) & is_target].mean())
        for s in sorted(set(signers))
        if ((signer_arr == s) & is_target).any()
    }
    confusion = np.zeros((len(class_names), len(class_names)), dtype=int)
    for t, p in zip(y, pred, strict=True):
        confusion[t, p] += 1

    return Evaluation(
        n=len(y),
        accuracy=float((pred == y).mean()),
        macro_f1=f1,
        macro_f1_ci=ci,
        top3=float(np.mean(top3_hits)) if top3_hits else 0.0,
        far=far,
        wrong_rate=wrong,
        coverage=coverage,
        ece=expected_calibration_error(probs, y),
        min_signer_accuracy=min(per_signer.values()) if per_signer else 0.0,
        per_class={
            class_names[k]: {"precision": p, "recall": r, "f1": f, "support": n}
            for k, (p, r, f, n) in per.items()
        },
        per_signer=per_signer,
        confusion=confusion.tolist(),
        class_names=list(class_names),
    )
