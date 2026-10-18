from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tests.conftest import SYNTHETIC_MODEL_ID, build_synthetic_model, load_replay
from vsl_backend.inference.model_registry import ModelLoadError
from vsl_backend.inference.template_model import load_template_model
from vsl_backend.recognition.classifiers import TemplateClassifier
from vsl_features.frames import parse_frame
from vsl_features.normalize import sequence_features
from vsl_features.segmentation import UtteranceSegmenter


def test_roundtrip_and_card(artifacts_dir: Path) -> None:
    model = load_template_model(artifacts_dir, SYNTHETIC_MODEL_ID)

    assert model.card.developer_only and model.card.distribution == "private"
    assert [label.gloss_id for label in model.labels] == ["SYN_A", "SYN_B", "SYN_C"]
    assert len(model.templates) == 9
    assert model.calibration.temperature > 0 and model.calibration.max_distance > 0


def test_no_pickle_in_npz(artifacts_dir: Path) -> None:
    path = artifacts_dir / "sign" / SYNTHETIC_MODEL_ID / "templates.npz"
    with np.load(path, allow_pickle=False) as npz:
        assert all(npz[k].dtype != object for k in npz.files)


def test_tampered_file_is_rejected(artifacts_dir: Path) -> None:
    labels = artifacts_dir / "sign" / SYNTHETIC_MODEL_ID / "labels.json"
    labels.write_text(
        labels.read_text(encoding="utf-8").replace("SYN_A", "SYN_X"), encoding="utf-8"
    )

    with pytest.raises(ModelLoadError, match=r"sha256 mismatch for 'labels\.json'"):
        load_template_model(artifacts_dir, SYNTHETIC_MODEL_ID)


@pytest.mark.parametrize("model_id", ["../etc", "a/b", "", ".hidden"])
def test_path_traversal_ids_are_rejected(tmp_path: Path, model_id: str) -> None:
    with pytest.raises(ModelLoadError, match="invalid model id"):
        load_template_model(tmp_path, model_id)


def test_feature_spec_mismatch_is_rejected(tmp_path: Path) -> None:
    directory = build_synthetic_model(tmp_path)
    card_path = directory / "model_card.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    card["feature_spec_version"] = "fs-0"
    card_path.write_text(json.dumps(card), encoding="utf-8")

    with pytest.raises(ModelLoadError, match="feature spec fs-0"):
        load_template_model(tmp_path, SYNTHETIC_MODEL_ID)


def test_classifies_the_synthetic_replay_correctly(artifacts_dir: Path) -> None:
    replay = load_replay()
    aspect = replay["image_width"] / replay["image_height"]
    classifier = TemplateClassifier(load_template_model(artifacts_dir, SYNTHETIC_MODEL_ID))
    segmenter = UtteranceSegmenter(aspect)

    decisions = []
    for raw in replay["frames"]:
        utterance = segmenter.push(parse_frame(raw))
        if utterance is not None:
            decisions.append(classifier.classify(sequence_features(utterance.frames, aspect)))

    assert [d.top[0].gloss_id for d in decisions] == [s["label"] for s in replay["segments"]]
    assert all(d.status == "confident" for d in decisions)


def test_unrelated_motion_is_rejected(artifacts_dir: Path) -> None:
    classifier = TemplateClassifier(load_template_model(artifacts_dir, SYNTHETIC_MODEL_ID))
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 3, (30, classifier._model.templates[0][1].shape[1])).astype(np.float32)

    assert classifier.classify(noise).status == "rejected"
