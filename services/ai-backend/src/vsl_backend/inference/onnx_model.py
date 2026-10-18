"""ONNX sign model (Phase 5): save, verify and load.

Files (docs/AI_ML_STRATEGY.md §8; no pickle, ADR-007):
    model.onnx        input `features` (1, time, feature_dim) float32 → `logits` (1, classes)
                      normalisation is inside the graph
    labels.json       [{gloss_id, text_vi, icon}], including __background__ / __distractor__
    calibration.json  {temperature, threshold, margin, floor} from the G5 operating point
    model_card.json   versions, dataset fingerprint, metrics + sha256 of the files above

`onnxruntime` is imported only when a model is loaded, so mock mode on the M1
never imports it (ADR-016).
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from vsl_backend.inference.model_registry import (
    ExtractorInfo,
    ModelCard,
    ModelLoadError,
    load_card,
    sha256_file,
)
from vsl_backend.schemas.recognition import LabelInfo
from vsl_features import FEATURE_SPEC

FloatArray = NDArray[np.float32]
# (1, time, feature_dim) → (1, classes)
Runner = Callable[[FloatArray], NDArray[np.floating[Any]]]
SessionFactory = Callable[[Path], Runner]

# Leave CPU cores for Chrome + MediaPipe on the laptop.
ORT_THREADS = 2


@dataclass(frozen=True)
class OnnxCalibration:
    temperature: float
    threshold: float
    margin: float
    floor: float


@dataclass(frozen=True)
class OnnxModel:
    card: ModelCard
    labels: list[LabelInfo]
    calibration: OnnxCalibration
    run: Runner


def save_onnx_model(
    out_dir: Path,
    model_id: str,
    onnx_file: Path,
    labels: list[LabelInfo],
    calibration: OnnxCalibration,
    *,
    vocabulary_version: str,
    extractor_version: str,
    extractor_backend: str,
    developer_only: bool,
    distribution: Literal["public", "private"] = "private",
    dataset: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
) -> Path:
    directory = out_dir / "sign" / model_id
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(onnx_file, directory / "model.onnx")
    (directory / "labels.json").write_text(
        json.dumps([label.model_dump() for label in labels], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (directory / "calibration.json").write_text(
        json.dumps(asdict(calibration), indent=2), encoding="utf-8"
    )
    files = ["model.onnx", "labels.json", "calibration.json"]
    card = ModelCard(
        model_id=model_id,
        kind="onnx",
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        feature_spec_version=FEATURE_SPEC.version,
        vocabulary_version=vocabulary_version,
        extractor=ExtractorInfo(version=extractor_version, backend=extractor_backend),
        developer_only=developer_only,
        distribution=distribution,
        files={name: sha256_file(directory / name) for name in files},
        dataset=dataset,
        metrics=metrics,
    )
    (directory / "model_card.json").write_text(card.model_dump_json(indent=2), encoding="utf-8")
    return directory


def ort_session(path: Path) -> Runner:
    try:
        import onnxruntime as ort
    except ImportError:
        raise ModelLoadError(
            "onnxruntime is not installed: start with uv run --extra train (or --extra onnx)"
        ) from None
    options = ort.SessionOptions()
    options.intra_op_num_threads = ORT_THREADS
    try:
        session = ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )
    except Exception:  # onnxruntime raises its own exception types
        raise ModelLoadError("model.onnx could not be loaded") from None
    name = session.get_inputs()[0].name

    def run(features: FloatArray) -> NDArray[np.floating[Any]]:
        result: NDArray[np.floating[Any]] = session.run(None, {name: features})[0]
        return result

    return run


def load_onnx_model(
    artifacts_dir: Path, model_id: str, session_factory: SessionFactory = ort_session
) -> OnnxModel:
    card, directory = load_card(artifacts_dir, model_id, "onnx")
    if "model.onnx" not in card.files:
        raise ModelLoadError("model_card.json does not list model.onnx")
    try:
        labels = [
            LabelInfo.model_validate(item)
            for item in json.loads((directory / "labels.json").read_text(encoding="utf-8"))
        ]
        calibration = OnnxCalibration(
            **json.loads((directory / "calibration.json").read_text(encoding="utf-8"))
        )
    except (KeyError, ValueError, TypeError):
        raise ModelLoadError("onnx model files are invalid") from None
    if not labels or calibration.temperature <= 0:
        raise ModelLoadError("onnx model files are invalid")
    run = session_factory(directory / "model.onnx")
    probe = np.zeros((1, 8, FEATURE_SPEC.feature_dim), dtype=np.float32)
    try:
        shape = np.asarray(run(probe)).shape
    except Exception:  # a model built for another feature dimension fails here
        raise ModelLoadError("model.onnx does not accept the feature spec input") from None
    if shape != (1, len(labels)):
        raise ModelLoadError(f"model output {shape} does not match {len(labels)} labels")
    return OnnxModel(card, labels, calibration, run)
