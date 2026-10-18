"""Resolve and verify model artifacts (docs/AI_ML_STRATEGY.md §8, ADR-007).

`VSL_SIGN_MODEL_ID` → `model-artifacts/sign/<id>/`. Every file listed in
`model_card.json` must match its sha256 before anything is loaded.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from vsl_features import FEATURE_SPEC

MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ModelLoadError(Exception):
    """Raised with a message that is safe to show in health details."""


class ExtractorInfo(BaseModel):
    version: str
    backend: str


class ModelCard(BaseModel):
    model_id: str
    kind: Literal["template-dtw", "onnx"]
    created_at: str
    feature_spec_version: str
    vocabulary_version: str
    extractor: ExtractorInfo
    developer_only: bool
    distribution: Literal["public", "private"]
    files: dict[str, str]  # file name → sha256


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_dir(artifacts_dir: Path, model_id: str) -> Path:
    if not MODEL_ID_PATTERN.fullmatch(model_id):
        raise ModelLoadError("invalid model id")
    return artifacts_dir / "sign" / model_id


def load_card(artifacts_dir: Path, model_id: str, expected_kind: str) -> tuple[ModelCard, Path]:
    directory = model_dir(artifacts_dir, model_id)
    card_path = directory / "model_card.json"
    if not card_path.is_file():
        raise ModelLoadError(f"model '{model_id}' not found")
    try:
        card = ModelCard.model_validate(json.loads(card_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError):
        raise ModelLoadError("model_card.json is invalid") from None
    if card.model_id != model_id:
        raise ModelLoadError("model_card.json model_id does not match the directory")
    if card.kind != expected_kind:
        raise ModelLoadError(f"model kind '{card.kind}' does not match mode '{expected_kind}'")
    if card.feature_spec_version != FEATURE_SPEC.version:
        raise ModelLoadError(
            f"feature spec {card.feature_spec_version} != server {FEATURE_SPEC.version}"
        )
    for name, expected in card.files.items():
        path = directory / name
        if Path(name).name != name or not path.is_file():
            raise ModelLoadError(f"missing artifact file '{name}'")
        if sha256_file(path) != expected:
            raise ModelLoadError(f"sha256 mismatch for '{name}'")
    return card, directory
