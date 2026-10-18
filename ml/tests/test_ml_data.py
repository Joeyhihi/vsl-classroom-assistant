"""Manifest → examples on a synthetic dataset in a temp DATA_ROOT (no real data)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from vsl_features.dataset import Dataset, ReviewEvent
from vsl_features.synth import IMAGE_HEIGHT, IMAGE_WIDTH, Variation, synth_rest, synth_sign
from vsl_features.vocabulary import load_vocabulary
from vsl_ml.data import BACKGROUND, DISTRACTOR, load_manifest_examples, synthetic_examples

VOCAB = Path(__file__).resolve().parents[1] / "vocabulary" / "vocabulary.dev.json"


def write(ds: Dataset, label: str, kind: str, frames: list, session: str) -> str:  # type: ignore[type-arg]
    record = ds.write_sample(
        frames,
        signer_id="DEV-01",
        session_id=session,
        label=label,
        sample_kind=kind,  # type: ignore[arg-type]
        consent_id="SELF",
        consent_scopes=["landmarks"],
        dominant_hand="right",
        conditions={},
        take_ms=3000,
        image_w=IMAGE_WIDTH,
        image_h=IMAGE_HEIGHT,
        extractor_version="synthetic",
        extractor_backend="synthetic",
    )
    return record.sample_id


def test_only_reviewed_samples_are_used_with_rejection_classes(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    ds = Dataset(tmp_path)
    session = "S20261018-090000-aaaa"
    sign = synth_rest(0, 300, 15, rng) + synth_sign("SYN_A", 400, 15, rng, Variation())
    sign += synth_rest(sign[-1].t_ms + 66.7, 900, 15, rng)
    ids = {
        "target": write(ds, "DEV_01", "target", sign, session),
        "distractor": write(ds, "DST_01", "distractor", sign, session),
        "background": write(ds, "REST_DESK", "background", synth_rest(0, 2000, 15, rng), session),
        "pending": write(ds, "DEV_02", "target", sign, session),
        "rejected": write(ds, "DEV_03", "target", sign, session),
    }
    for name in ("target", "distractor", "background"):
        ds.add_review(ReviewEvent(ids[name], "accepted", "DEV-01", "t"))
    ds.add_review(ReviewEvent(ids["rejected"], "rejected", "DEV-01", "t", reject_reason="other"))

    data = load_manifest_examples(tmp_path, load_vocabulary(VOCAB))

    assert sorted(e.label for e in data.examples) == sorted([BACKGROUND, DISTRACTOR, "DEV_01"])
    target = next(e for e in data.examples if e.label == "DEV_01")
    assert len(target.features) < len(sign)  # trimmed by the live segmenter
    assert len(data.fingerprint) == 64 and data.extractor_version == "synthetic"


def test_synthetic_examples_cover_every_role() -> None:
    data = synthetic_examples(signers=2, takes=1)
    assert {e.label for e in data.examples} == {"SYN_A", "SYN_B", DISTRACTOR, BACKGROUND}
    assert all(len(e.features) >= 5 for e in data.examples)
