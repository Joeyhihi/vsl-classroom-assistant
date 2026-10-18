from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from vsl_features.dataset import (
    Dataset,
    DatasetError,
    ReviewEvent,
    SampleRecord,
    arrays_to_frames,
    check_consent,
    ensure_outside_repo,
    frames_to_arrays,
    load_frames,
    new_session_id,
    record_from_dict,
)
from vsl_features.frames import Frame
from vsl_features.synth import synth_rest, synth_sign
from vsl_features.vocabulary import load_vocabulary

REPO = Path(__file__).resolve().parents[3]
SESSION = "S20261018-090000-0a1b"
COMMON: dict[str, Any] = {
    "signer_id": "DEV-01",
    "session_id": SESSION,
    "consent_id": "SELF",
    "consent_scopes": ["landmarks"],
    "dominant_hand": "right",
    "conditions": {"lighting": "normal"},
    "image_w": 640,
    "image_h": 480,
    "extractor_version": "synthetic",
    "extractor_backend": "synthetic",
}


def sign_frames(seed: int = 0) -> list[Frame]:
    return synth_sign("SYN_A", 0, 15, np.random.default_rng(seed))


def write(ds: Dataset, label: str = "DEV_01", seed: int = 0) -> SampleRecord:
    return ds.write_sample(
        sign_frames(seed), label=label, sample_kind="target", take_ms=3000, **COMMON
    )


def test_npz_roundtrip_keeps_missing_parts() -> None:
    frames = sign_frames()
    frames[3] = Frame(frames[3].t_ms, frames[3].pose, None, frames[3].right_hand, None)
    back = arrays_to_frames(frames_to_arrays(frames))
    assert len(back) == len(frames)
    assert back[3].left_hand is None and back[3].face is None
    assert back[3].right_hand is not None
    np.testing.assert_allclose(back[5].pose, frames[5].pose)  # type: ignore[arg-type]


def test_write_sample_layout_and_manifest(tmp_path: Path) -> None:
    ds = Dataset(tmp_path)
    record = write(ds)

    assert record.sample_id == f"{SESSION}-001"
    assert record.file == f"landmarks/DEV-01/{SESSION}/{SESSION}-001.npz"
    assert (tmp_path / record.file).is_file()
    assert not list(tmp_path.rglob("*.part"))
    assert 14 < record.fps < 16 and record.n_frames == len(sign_frames())
    with np.load(tmp_path / record.file, allow_pickle=False) as npz:
        assert all(npz[k].dtype != object for k in npz.files)
    assert len(load_frames(tmp_path / record.file)) == record.n_frames
    assert write(ds, seed=1).sample_id == f"{SESSION}-002"
    assert ds.verify() == []


def test_sample_counter_survives_a_new_dataset_object(tmp_path: Path) -> None:
    write(Dataset(tmp_path))
    assert write(Dataset(tmp_path), seed=1).sample_id.endswith("-002")


def test_reviews_fold_into_the_current_view(tmp_path: Path) -> None:
    ds = Dataset(tmp_path)
    a, b, c = write(ds), write(ds, seed=1), write(ds, seed=2)
    ds.add_review(ReviewEvent(a.sample_id, "accepted", "DEV-01", "t1"))
    ds.add_review(ReviewEvent(b.sample_id, "rejected", "DEV-01", "t1", reject_reason="incomplete"))
    ds.add_review(ReviewEvent(c.sample_id, "accepted", "DEV-01", "t1"))
    ds.add_review(ReviewEvent(c.sample_id, "relabelled", "DEV-01", "t2", relabel_to="DEV_02"))

    views = {v.record.sample_id: v for v in ds.samples()}
    assert views[a.sample_id].usable and views[a.sample_id].label == "DEV_01"
    assert not views[b.sample_id].usable and views[b.sample_id].reject_reason == "incomplete"
    assert views[c.sample_id].status == "relabelled" and views[c.sample_id].label == "DEV_02"


@pytest.mark.parametrize(
    "event",
    [
        ReviewEvent("x", "rejected", "DEV-01", "t"),  # no reason
        ReviewEvent("x", "relabelled", "DEV-01", "t", relabel_to="bad label"),
        ReviewEvent("x", "pending", "DEV-01", "t"),
    ],
)
def test_invalid_reviews_are_refused(tmp_path: Path, event: ReviewEvent) -> None:
    ds = Dataset(tmp_path)
    record = write(ds)
    with pytest.raises(DatasetError):
        ds.add_review(
            ReviewEvent(
                record.sample_id,
                event.status,
                event.reviewer,
                event.at,
                event.reject_reason,
                event.relabel_to,
            )
        )


def test_delete_removes_file_and_hides_sample(tmp_path: Path) -> None:
    ds = Dataset(tmp_path)
    record = write(ds)
    assert ds.delete_sample(record.sample_id, "withdrawal")
    assert not (tmp_path / record.file).exists()
    assert ds.samples() == []
    assert not ds.delete_sample(record.sample_id, "withdrawal")
    tombstones = (tmp_path / "manifests" / "tombstones.jsonl").read_text(encoding="utf-8")
    assert record.sample_id in tombstones and "withdrawal" in tombstones
    with pytest.raises(DatasetError, match="unknown or deleted"):
        ds.add_review(ReviewEvent(record.sample_id, "accepted", "DEV-01", "t"))


def test_verify_detects_tampering(tmp_path: Path) -> None:
    ds = Dataset(tmp_path)
    record = write(ds)
    (tmp_path / record.file).write_bytes(b"tampered")
    assert ds.verify() == [f"{record.sample_id}: sha256 mismatch"]


@pytest.mark.parametrize(
    ("signer", "consent", "third_party", "error"),
    [
        ("DEV-01", "SELF", False, None),
        ("SGN-0001", "SELF", False, "only for the developer"),
        ("SGN-0001", "C-1234", False, "blocked until the consent package"),
        ("SGN-0001", "C-1234", True, None),
        ("Nguyen Van A", "SELF", False, "pseudonymous"),
        ("DEV-01", "yes", False, "SELF or C-"),
    ],
)
def test_consent_rule(signer: str, consent: str, third_party: bool, error: str | None) -> None:
    if error is None:
        check_consent(signer, consent, third_party)
    else:
        with pytest.raises(DatasetError, match=error):
            check_consent(signer, consent, third_party)


def test_data_root_inside_a_git_checkout_is_refused(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with pytest.raises(DatasetError, match="outside the repository"):
        ensure_outside_repo(tmp_path / "data")
    ensure_outside_repo(tmp_path.parent / "elsewhere")  # no .git above: fine


def test_session_ids_have_the_expected_shape() -> None:
    sid = new_session_id(np.random.default_rng(0))
    assert (
        record_from_dict(
            dict(
                json.loads(
                    (REPO / "ml/metadata/manifest.example.jsonl").read_text().splitlines()[0]
                ),
                session_id=sid,
                sample_id=f"{sid}-001",
            )
        ).session_id
        == sid
    )


def test_example_manifest_and_schema_match_the_dataclass() -> None:
    lines = (REPO / "ml/metadata/manifest.example.jsonl").read_text(encoding="utf-8").splitlines()
    records = [record_from_dict(json.loads(line)) for line in lines]
    assert {r.sample_kind for r in records} == {"target", "background"}
    schema = json.loads((REPO / "ml/metadata/manifest.schema.json").read_text(encoding="utf-8"))
    names = {f.name for f in fields(SampleRecord)}
    assert set(schema["properties"]) == names == set(schema["required"])


def test_manifest_rows_reject_unknown_or_missing_fields() -> None:
    row = json.loads((REPO / "ml/metadata/manifest.example.jsonl").read_text().splitlines()[0])
    with pytest.raises(DatasetError, match="unknown fields"):
        record_from_dict(row | {"name": "Nguyen Van A"})
    del row["sha256"]
    with pytest.raises(DatasetError, match="missing fields"):
        record_from_dict(row)


def test_dev_vocabulary_is_valid_and_marked_developer_only() -> None:
    vocab = load_vocabulary(REPO / "ml/vocabulary/vocabulary.dev.json")
    assert vocab.developer_only
    kinds = {i.sample_kind for i in vocab.items}
    assert kinds == {"target", "distractor", "background"}
    assert vocab.get("REST_DESK") is not None


def test_background_rest_takes_are_storable(tmp_path: Path) -> None:
    ds = Dataset(tmp_path)
    rest = synth_rest(0, 3000, 15, np.random.default_rng(4))
    record = ds.write_sample(
        rest, label="REST_DESK", sample_kind="background", take_ms=3000, **COMMON
    )
    assert record.sample_kind == "background"
