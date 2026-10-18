"""Template (DTW nearest-neighbour) model: build, save and load.

This is the Phase 3 walking-skeleton classifier, built from the developer's own
3-5 signs on the Windows laptop. It is a pipeline check, never the real model;
its model card is always `developer_only` and `private`.

Files (no pickle, ADR-007):
    templates.npz     data (N x D float32), offsets (K+1 int64), label_index (K int64)
    labels.json       [{gloss_id, text_vi, icon}]
    calibration.json  {temperature, max_distance, threshold, margin, floor}
    model_card.json   versions + sha256 of the three files above
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

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
from vsl_features.dtw import dtw_distance

FloatArray = NDArray[np.float32]


@dataclass(frozen=True)
class Calibration:
    temperature: float
    max_distance: float
    threshold: float = 0.7
    margin: float = 0.2
    floor: float = 0.35


@dataclass(frozen=True)
class TemplateModel:
    card: ModelCard
    labels: list[LabelInfo]
    templates: list[tuple[int, FloatArray]]  # (label index, sequence)
    calibration: Calibration


def calibrate(templates: list[tuple[int, FloatArray]]) -> Calibration:
    """Dev heuristic from leave-one-out template distances (not a G5 calibration)."""
    same: list[float] = []
    other: list[float] = []
    for i, (label_i, seq_i) in enumerate(templates):
        for j, (label_j, seq_j) in enumerate(templates):
            if i < j:
                (same if label_i == label_j else other).append(dtw_distance(seq_i, seq_j))
    if same:
        temperature = max(0.05, float(np.median(same)) * 0.5)
        max_distance = float(max(same)) * 1.5
    else:  # one template per class
        reference = float(np.median(other)) if other else 1.0
        temperature, max_distance = max(0.05, reference * 0.25), reference * 0.6
    return Calibration(temperature=temperature, max_distance=max_distance)


def save_template_model(
    out_dir: Path,
    model_id: str,
    labels: list[LabelInfo],
    templates: list[tuple[int, FloatArray]],
    extractor_version: str,
    extractor_backend: str,
    calibration: Calibration | None = None,
) -> Path:
    if not templates:
        raise ValueError("no templates")
    directory = out_dir / "sign" / model_id
    directory.mkdir(parents=True, exist_ok=True)
    lengths = [len(seq) for _, seq in templates]
    np.savez(
        directory / "templates.npz",
        data=np.concatenate([seq for _, seq in templates]).astype(np.float32),
        offsets=np.concatenate([[0], np.cumsum(lengths)]).astype(np.int64),
        label_index=np.array([label for label, _ in templates], dtype=np.int64),
    )
    (directory / "labels.json").write_text(
        json.dumps([label.model_dump() for label in labels], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    cal = calibration or calibrate(templates)
    (directory / "calibration.json").write_text(json.dumps(asdict(cal), indent=2), encoding="utf-8")
    files = ["templates.npz", "labels.json", "calibration.json"]
    card = ModelCard(
        model_id=model_id,
        kind="template-dtw",
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        feature_spec_version=FEATURE_SPEC.version,
        vocabulary_version="dev-local",
        extractor=ExtractorInfo(version=extractor_version, backend=extractor_backend),
        developer_only=True,
        distribution="private",
        files={name: sha256_file(directory / name) for name in files},
    )
    (directory / "model_card.json").write_text(card.model_dump_json(indent=2), encoding="utf-8")
    return directory


def load_template_model(artifacts_dir: Path, model_id: str) -> TemplateModel:
    card, directory = load_card(artifacts_dir, model_id, "template-dtw")
    try:
        with np.load(directory / "templates.npz", allow_pickle=False) as npz:
            data, offsets, label_index = npz["data"], npz["offsets"], npz["label_index"]
        labels = [
            LabelInfo.model_validate(item)
            for item in json.loads((directory / "labels.json").read_text(encoding="utf-8"))
        ]
        calibration = Calibration(
            **json.loads((directory / "calibration.json").read_text(encoding="utf-8"))
        )
    except (KeyError, ValueError, TypeError):
        raise ModelLoadError("template model files are invalid") from None
    if data.ndim != 2 or data.shape[1] != FEATURE_SPEC.feature_dim:
        raise ModelLoadError("template feature dimension does not match the feature spec")
    if len(offsets) != len(label_index) + 1 or (label_index >= len(labels)).any():
        raise ModelLoadError("template index is inconsistent")
    templates = [
        (int(label_index[k]), data[offsets[k] : offsets[k + 1]].astype(np.float32))
        for k in range(len(label_index))
    ]
    return TemplateModel(card, labels, templates, calibration)
