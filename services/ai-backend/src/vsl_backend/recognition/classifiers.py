"""Classifier protocol, the dev-only mock classifier (ADR-016) and the template classifier.

Classifiers receive the normalised feature sequence of one closed utterance
(`vsl_features.normalize.sequence_features`) and return a decision. The mock
classifier imports no ML libraries, so the frontend and WS protocol can be
developed on the M1 Mac without models.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
from numpy.typing import NDArray

from vsl_backend.config import MockScript, Settings
from vsl_backend.inference.model_registry import ModelLoadError
from vsl_backend.inference.template_model import TemplateModel, load_template_model
from vsl_backend.schemas.recognition import LabelInfo, ModelInfo
from vsl_features import FEATURE_SPEC
from vsl_features.decoding import DecisionPolicy, softmax
from vsl_features.dtw import dtw_distance

logger = logging.getLogger(__name__)

DecisionStatus = Literal["confident", "uncertain", "rejected"]
Features = NDArray[np.float32]


@dataclass(frozen=True)
class ScoredLabel:
    gloss_id: str
    text_vi: str
    icon: str
    score: float


@dataclass(frozen=True)
class Decision:
    status: DecisionStatus
    top: tuple[ScoredLabel, ...]


class Classifier(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def info(self) -> ModelInfo: ...

    @property
    def labels(self) -> list[LabelInfo]: ...

    def classify(self, features: Features) -> Decision: ...


# Synthetic labels for development only. These are NOT validated VSL items;
# the real vocabulary comes from expert review (docs/DATASET_AND_ANNOTATION.md).
_MOCK_LABELS = (
    LabelInfo(gloss_id="MOCK_0001", text_vi="Xin chào", icon="wave"),
    LabelInfo(gloss_id="MOCK_0002", text_vi="Cảm ơn", icon="thanks"),
    LabelInfo(gloss_id="MOCK_0003", text_vi="Xin nhắc lại", icon="repeat"),
)

# One full cycle exercises every UI state: confident → uncertain → rejected.
_MOCK_SCRIPT: tuple[tuple[DecisionStatus, tuple[float, float, float]], ...] = (
    ("confident", (0.91, 0.05, 0.02)),
    ("uncertain", (0.48, 0.31, 0.12)),
    ("rejected", (0.22, 0.20, 0.18)),
)


class MockClassifier:
    """Deterministic scripted decisions; ignores its input."""

    def __init__(self, script: MockScript = "cycle") -> None:
        self.script = script
        self._step = 0

    @property
    def model_id(self) -> str:
        return "mock"

    @property
    def info(self) -> ModelInfo:
        return ModelInfo(
            model_id="mock",
            kind="mock",
            vocabulary_version="mock",
            feature_spec_version=FEATURE_SPEC.version,
            developer_only=True,
        )

    @property
    def labels(self) -> list[LabelInfo]:
        return list(_MOCK_LABELS)

    def classify(self, features: Features) -> Decision:
        status, scores = _MOCK_SCRIPT[self._step % len(_MOCK_SCRIPT)]
        # Rotate which label leads so consecutive confident results differ.
        offset = (self._step // len(_MOCK_SCRIPT)) % len(_MOCK_LABELS)
        labels = _MOCK_LABELS[offset:] + _MOCK_LABELS[:offset]
        self._step += 1
        top = tuple(
            ScoredLabel(gloss_id=label.gloss_id, text_vi=label.text_vi, icon=label.icon, score=s)
            for label, s in zip(labels, scores, strict=True)
        )
        return Decision(status=status, top=top)


class TemplateClassifier:
    """Nearest-template DTW classifier (P3 walking skeleton; developer data only)."""

    def __init__(self, model: TemplateModel) -> None:
        self._model = model
        self._policy = DecisionPolicy(
            threshold=model.calibration.threshold,
            margin=model.calibration.margin,
            floor=model.calibration.floor,
        )

    @property
    def model_id(self) -> str:
        return self._model.card.model_id

    @property
    def info(self) -> ModelInfo:
        card = self._model.card
        return ModelInfo(
            model_id=card.model_id,
            kind="template-dtw",
            vocabulary_version=card.vocabulary_version,
            feature_spec_version=card.feature_spec_version,
            developer_only=card.developer_only,
        )

    @property
    def labels(self) -> list[LabelInfo]:
        return list(self._model.labels)

    def classify(self, features: Features) -> Decision:
        labels = self._model.labels
        best = np.full(len(labels), np.inf)
        for label_index, template in self._model.templates:
            best[label_index] = min(best[label_index], dtw_distance(features, template))
        if not np.isfinite(best).any():
            return Decision("rejected", ())
        cal = self._model.calibration
        finite = np.where(np.isfinite(best), best, best[np.isfinite(best)].max() * 10)
        probs = softmax((-finite).tolist(), temperature=cal.temperature)
        order = np.argsort(finite)[:3]
        ranked = [(labels[i].gloss_id, probs[i]) for i in order]
        status = "rejected" if finite[order[0]] > cal.max_distance else self._policy.decide(ranked)
        top = tuple(
            ScoredLabel(labels[i].gloss_id, labels[i].text_vi, labels[i].icon, round(probs[i], 4))
            for i in order
        )
        return Decision(status, top)


@dataclass(frozen=True)
class ClassifierLoad:
    classifier: Classifier | None
    error: str | None = None


def build_classifier(settings: Settings) -> ClassifierLoad:
    """Load the configured classifier; failures leave the app in manual-only mode."""
    if settings.model_mode == "mock":
        return ClassifierLoad(MockClassifier(settings.mock_script))
    if settings.model_mode == "onnx":
        return ClassifierLoad(None, "not implemented until Phase 5")
    if not settings.sign_model_id:
        return ClassifierLoad(None, "VSL_SIGN_MODEL_ID is not set")
    try:
        model = load_template_model(settings.model_artifacts_dir, settings.sign_model_id)
    except ModelLoadError as exc:
        logger.warning("sign model unavailable: %s", exc)
        return ClassifierLoad(None, str(exc))
    return ClassifierLoad(TemplateClassifier(model))
