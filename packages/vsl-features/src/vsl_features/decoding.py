"""Decision policy and duplicate suppression (docs/API_CONTRACTS.md, prediction status)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

DecisionStatus = Literal["confident", "uncertain", "rejected"]
REJECTION_LABELS = frozenset({"__background__", "__distractor__"})


def softmax(logits: Sequence[float], temperature: float = 1.0) -> list[float]:
    z = np.asarray(logits, dtype=np.float64) / max(temperature, 1e-6)
    z = np.exp(z - z.max())
    return [float(v) for v in z / z.sum()]


@dataclass(frozen=True)
class DecisionPolicy:
    """Thresholds are set at gate G5 from validation data; these are dev defaults."""

    threshold: float = 0.7
    margin: float = 0.2
    floor: float = 0.35

    def decide(self, ranked: Sequence[tuple[str, float]]) -> DecisionStatus:
        """`ranked` is (label, calibrated probability), highest first."""
        if not ranked:
            return "rejected"
        top_label, top = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        if top_label in REJECTION_LABELS or top < self.floor:
            return "rejected"
        if top >= self.threshold and top - second >= self.margin:
            return "confident"
        return "uncertain"


class CooldownFilter:
    """Suppress the same top label repeated within `window_ms` (one sign held too long)."""

    def __init__(self, window_ms: float = 1500.0) -> None:
        self.window_ms = window_ms
        self._last: tuple[str, float] | None = None

    def allow(self, label: str, t_ms: float) -> bool:
        last = self._last
        if last is not None and last[0] == label and t_ms - last[1] < self.window_ms:
            return False
        self._last = (label, t_ms)
        return True
