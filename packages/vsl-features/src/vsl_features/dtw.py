"""Dynamic time warping for the template classifier (P3 sanity baseline)."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def dtw_distance(a: NDArray[np.float32], b: NDArray[np.float32], band: float = 0.25) -> float:
    """Mean per-step Euclidean cost along the best warping path.

    `band` is a Sakoe-Chiba window as a fraction of the longer sequence; it
    stops pathological warps and bounds the cost. Returns inf for empty input.
    """
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return float("inf")
    window = max(int(band * max(n, m)), abs(n - m)) + 1
    cost = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(axis=2))
    acc = np.full((n + 1, m + 1), np.inf)
    steps = np.zeros((n + 1, m + 1))
    acc[0, 0] = 0.0
    for i in range(1, n + 1):
        lo, hi = max(1, i - window), min(m, i + window)
        for j in range(lo, hi + 1):
            choices = (acc[i - 1, j - 1], acc[i - 1, j], acc[i, j - 1])
            k = int(np.argmin(choices))
            prev = ((i - 1, j - 1), (i - 1, j), (i, j - 1))[k]
            acc[i, j] = cost[i - 1, j - 1] + choices[k]
            steps[i, j] = steps[prev] + 1
    if not np.isfinite(acc[n, m]):
        return float("inf")
    return float(acc[n, m] / steps[n, m])
