"""DTW nearest-template baseline (the P3 classifier) scored like the neural models."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from vsl_features.dtw import dtw_distance
from vsl_ml.data import Example, FloatArray


def dtw_logits(
    templates: list[Example], seqs: list[FloatArray], class_names: list[str]
) -> NDArray[np.float64]:
    """Logits = -(distance to the nearest template of each class)."""
    index = {name: k for k, name in enumerate(class_names)}
    out = np.full((len(seqs), len(class_names)), np.inf)
    for i, seq in enumerate(seqs):
        for template in templates:
            k = index[template.label]
            out[i, k] = min(out[i, k], dtw_distance(seq, template.features))
    finite = out[np.isfinite(out)]
    worst = float(finite.max()) * 10 if finite.size else 1.0
    result: NDArray[np.float64] = -np.where(np.isfinite(out), out, worst)
    return result
