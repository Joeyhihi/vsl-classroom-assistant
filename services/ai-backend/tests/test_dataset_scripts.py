"""Phase 4 dataset scripts on a synthetic dataset in a temp DATA_ROOT (no real data)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from tests.conftest import REPO_ROOT
from vsl_backend.inference.template_model import load_template_model
from vsl_backend.recognition.classifiers import TemplateClassifier
from vsl_features.dataset import Dataset, ReviewEvent
from vsl_features.normalize import sequence_features
from vsl_features.synth import IMAGE_HEIGHT, IMAGE_WIDTH, Variation, synth_rest, synth_sign

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_templates
import dataset_report
import delete_recordings

VOCAB = REPO_ROOT / "ml" / "vocabulary" / "vocabulary.dev.json"
COMMON: dict[str, Any] = {
    "consent_id": "SELF",
    "consent_scopes": ["landmarks"],
    "dominant_hand": "right",
    "conditions": {"lighting": "normal"},
    "image_w": IMAGE_WIDTH,
    "image_h": IMAGE_HEIGHT,
    "extractor_version": "synthetic",
    "extractor_backend": "synthetic",
}
# The dev vocabulary's DEV_01..DEV_03 are recorded with the synthetic patterns A..C.
PATTERN = {"DEV_01": "SYN_A", "DEV_02": "SYN_B", "DEV_03": "SYN_C"}


def build_dataset(root: Path) -> Dataset:
    rng = np.random.default_rng(5)
    ds = Dataset(root)
    for session, signer in (
        ("S20261018-090000-aaaa", "DEV-01"),
        ("S20261018-100000-bbbb", "DEV-02"),
    ):
        for label, pattern in PATTERN.items():
            for _ in range(2):
                frames = synth_rest(0, 300, 15, rng)
                frames += synth_sign(
                    pattern, frames[-1].t_ms + 66.7, 15, rng, Variation.random(rng)
                )
                frames += synth_rest(frames[-1].t_ms + 66.7, 900, 15, rng)
                ds.write_sample(
                    frames,
                    signer_id=signer,
                    session_id=session,
                    label=label,
                    sample_kind="target",
                    take_ms=3000,
                    **COMMON,
                )
        ds.write_sample(
            synth_rest(0, 3000, 15, rng),
            signer_id=signer,
            session_id=session,
            label="REST_DESK",
            sample_kind="background",
            take_ms=3000,
            **COMMON,
        )
    return ds


def accept_all_but_one(ds: Dataset) -> str:
    views = ds.samples()
    rejected = views[0].record.sample_id
    for v in views:
        if v.record.sample_id == rejected:
            ds.add_review(
                ReviewEvent(rejected, "rejected", "DEV-01", "t", reject_reason="incomplete")
            )
        else:
            ds.add_review(ReviewEvent(v.record.sample_id, "accepted", "DEV-01", "t"))
    return rejected


def test_report_counts_and_segmenter_outcomes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ds = build_dataset(tmp_path)
    accept_all_but_one(ds)

    assert dataset_report.main(["--data-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Samples: **14** in 2 session(s)" in out
    assert "accepted 13" in out and "rejected 1" in out
    assert "DEV-01 (7), DEV-02 (7)" in out
    assert "| REST_DESK | background | 2 |" in out
    assert "Integrity: OK" in out
    assert "false starts" not in out  # rest takes do not start the segmenter
    assert len(list((tmp_path / "reports").glob("quality-*.md"))) == 1


def test_delete_is_a_dry_run_unless_confirmed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ds = build_dataset(tmp_path)
    assert delete_recordings.main(["--signer", "DEV-02", "--data-root", str(tmp_path)]) == 0
    assert "dry run" in capsys.readouterr().out
    assert len(ds.samples()) == 14

    assert (
        delete_recordings.main(["--signer", "DEV-02", "--data-root", str(tmp_path), "--yes"]) == 0
    )
    out = capsys.readouterr().out
    assert "deleted 7 sample(s)" in out and "identity register" in out
    assert {v.record.signer_id for v in ds.samples()} == {"DEV-01"}
    assert not (tmp_path / "landmarks" / "DEV-02").exists()  # empty folders removed
    assert ds.verify() == []


def test_delete_a_single_sample_with_cleanup_reason(tmp_path: Path) -> None:
    ds = build_dataset(tmp_path)
    sample = ds.samples()[3].record.sample_id
    delete_recordings.main(["--sample", sample, "--data-root", str(tmp_path), "--yes"])
    tombstones = (tmp_path / "manifests" / "tombstones.jsonl").read_text(encoding="utf-8")
    assert sample in tombstones and '"cleanup"' in tombstones


def test_scripts_refuse_a_data_root_inside_the_repo() -> None:
    with pytest.raises(SystemExit, match="outside the repository"):
        dataset_report.main(["--data-root", str(REPO_ROOT / "data"), "--no-save"])


def test_templates_from_manifest_use_accepted_targets_only(tmp_path: Path) -> None:
    data = tmp_path / "data"
    ds = build_dataset(data)
    rejected = accept_all_but_one(ds)
    artifacts = tmp_path / "artifacts"

    assert (
        build_templates.main(
            [
                "--model-id",
                "dev-manifest",
                "--from-manifest",
                "--data-root",
                str(data),
                "--vocabulary",
                str(VOCAB),
                "--out",
                str(artifacts),
            ]
        )
        == 0
    )
    model = load_template_model(artifacts, "dev-manifest")
    assert [label.gloss_id for label in model.labels] == ["DEV_01", "DEV_02", "DEV_03"]
    assert model.labels[0].text_vi == "Ký hiệu thử 1"  # text comes from the vocabulary
    assert len(model.templates) == 11  # 12 targets - 1 rejected; background excluded
    assert rejected.endswith("-001")

    classifier = TemplateClassifier(model)
    rng = np.random.default_rng(99)
    aspect = IMAGE_WIDTH / IMAGE_HEIGHT
    for label, pattern in PATTERN.items():
        decision = classifier.classify(
            sequence_features(synth_sign(pattern, 0, 15, rng, Variation.random(rng)), aspect)
        )
        assert decision.top[0].gloss_id == label
