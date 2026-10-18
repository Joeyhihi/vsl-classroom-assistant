"""ONNX model artifacts and classifier with a fake runner (no onnxruntime on the M1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from vsl_backend.config import Settings
from vsl_backend.inference.model_registry import ModelLoadError
from vsl_backend.inference.onnx_model import (
    OnnxCalibration,
    Runner,
    load_onnx_model,
    save_onnx_model,
)
from vsl_backend.recognition.classifiers import OnnxClassifier, build_classifier
from vsl_backend.schemas.recognition import LabelInfo
from vsl_features import FEATURE_SPEC

MODEL_ID = "onnx-test"
LABELS = [
    LabelInfo(gloss_id="DEV_01", text_vi="Một", icon="hand"),
    LabelInfo(gloss_id="DEV_02", text_vi="Hai", icon="hand"),
    LabelInfo(gloss_id="__background__", text_vi="Không phải ký hiệu", icon="rest"),
]
FEATURES = np.zeros((10, FEATURE_SPEC.feature_dim), dtype=np.float32)


def fixed(logits: list[float]) -> Any:
    def factory(path: Path) -> Runner:
        def run(x: NDArray[np.float32]) -> NDArray[np.float64]:
            assert x.dtype == np.float32 and x.shape[0] == 1
            assert x.shape[2] == FEATURE_SPEC.feature_dim
            return np.array([logits])

        return run

    return factory


@pytest.fixture
def artifacts(tmp_path: Path) -> Path:
    onnx = tmp_path / "fake.onnx"
    onnx.write_bytes(b"not a real model")  # the runner is faked
    save_onnx_model(
        tmp_path / "artifacts",
        MODEL_ID,
        onnx,
        LABELS,
        OnnxCalibration(temperature=1.0, threshold=0.7, margin=0.2, floor=0.35),
        vocabulary_version="dev-1",
        extractor_version="synthetic",
        extractor_backend="synthetic",
        developer_only=True,
        dataset={"dataset_version": "abc"},
        metrics={"arch": "gru"},
    )
    return tmp_path / "artifacts"


def test_card_lists_every_file_with_sha256(artifacts: Path) -> None:
    card = json.loads((artifacts / "sign" / MODEL_ID / "model_card.json").read_text("utf-8"))
    assert card["kind"] == "onnx" and card["distribution"] == "private"
    assert set(card["files"]) == {"model.onnx", "labels.json", "calibration.json"}
    assert card["metrics"] == {"arch": "gru"} and card["dataset"]["dataset_version"] == "abc"


def test_confident_sign(artifacts: Path) -> None:
    model = load_onnx_model(artifacts, MODEL_ID, fixed([6.0, 1.0, 0.0]))
    decision = OnnxClassifier(model).classify(FEATURES)

    assert decision.status == "confident"
    assert [t.gloss_id for t in decision.top] == ["DEV_01", "DEV_02"]


def test_background_win_is_rejected_and_hidden(artifacts: Path) -> None:
    classifier = OnnxClassifier(load_onnx_model(artifacts, MODEL_ID, fixed([1.0, 0.0, 6.0])))
    decision = classifier.classify(FEATURES)

    assert decision.status == "rejected"
    assert "__background__" not in {t.gloss_id for t in decision.top}
    assert [label.gloss_id for label in classifier.labels] == ["DEV_01", "DEV_02"]
    assert classifier.info.kind == "onnx" and classifier.info.developer_only


def test_close_scores_are_uncertain(artifacts: Path) -> None:
    model = load_onnx_model(artifacts, MODEL_ID, fixed([2.0, 1.8, -3.0]))
    assert OnnxClassifier(model).classify(FEATURES).status == "uncertain"


def test_empty_utterance_is_rejected(artifacts: Path) -> None:
    model = load_onnx_model(artifacts, MODEL_ID, fixed([6.0, 1.0, 0.0]))
    assert OnnxClassifier(model).classify(FEATURES[:0]).status == "rejected"


def test_wrong_output_size_is_refused(artifacts: Path) -> None:
    with pytest.raises(ModelLoadError, match="does not match 3 labels"):
        load_onnx_model(artifacts, MODEL_ID, fixed([1.0, 2.0]))


def test_tampered_model_is_refused(artifacts: Path) -> None:
    (artifacts / "sign" / MODEL_ID / "model.onnx").write_bytes(b"swapped")
    with pytest.raises(ModelLoadError, match=r"sha256 mismatch for 'model\.onnx'"):
        load_onnx_model(artifacts, MODEL_ID, fixed([1.0, 2.0, 3.0]))


def test_template_mode_refuses_an_onnx_card(artifacts: Path) -> None:
    settings = Settings(
        _env_file=None,
        model_mode="template",
        sign_model_id=MODEL_ID,
        model_artifacts_dir=artifacts,
    )
    load = build_classifier(settings)
    assert load.classifier is None and load.error and "does not match mode" in load.error


def test_onnx_mode_reports_load_errors(artifacts: Path) -> None:
    settings = Settings(
        _env_file=None,
        model_mode="onnx",
        sign_model_id=MODEL_ID,
        model_artifacts_dir=artifacts,
    )
    # No onnxruntime on the M1, and the file is not a real model elsewhere.
    load = build_classifier(settings)
    assert load.classifier is None and load.error
