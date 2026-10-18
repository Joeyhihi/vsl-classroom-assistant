"""Classifier protocol and the dev-only mock classifier (ADR-016).

The mock classifier imports no ML libraries and produces scripted decisions so
the frontend and WS protocol can be developed on the M1 Mac without models.
`TemplateClassifier` (P3) and `OnnxClassifier` (P5) will implement the same
protocol.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from vsl_backend.config import MockScript, Settings

DecisionStatus = Literal["confident", "uncertain", "rejected"]


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

    def classify(self, utterance: Sequence[object]) -> Decision: ...


# Synthetic labels for development only. These are NOT validated VSL items;
# the real vocabulary comes from expert review (docs/DATASET_AND_ANNOTATION.md).
_MOCK_LABELS = (
    ("MOCK_0001", "Xin chào", "wave"),
    ("MOCK_0002", "Cảm ơn", "thanks"),
    ("MOCK_0003", "Xin nhắc lại", "repeat"),
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

    def classify(self, utterance: Sequence[object]) -> Decision:
        status, scores = _MOCK_SCRIPT[self._step % len(_MOCK_SCRIPT)]
        # Rotate which label leads so consecutive confident results differ.
        offset = (self._step // len(_MOCK_SCRIPT)) % len(_MOCK_LABELS)
        labels = _MOCK_LABELS[offset:] + _MOCK_LABELS[:offset]
        self._step += 1
        top = tuple(
            ScoredLabel(gloss_id=g, text_vi=t, icon=i, score=s)
            for (g, t, i), s in zip(labels, scores, strict=True)
        )
        return Decision(status=status, top=top)


def build_classifier(settings: Settings) -> Classifier | None:
    """Return the configured classifier, or None if it is unavailable.

    Phase 1 implements only mock mode; template (P3) and onnx (P5) report
    unavailable so the app runs in manual-only mode.
    """
    if settings.model_mode == "mock":
        return MockClassifier(settings.mock_script)
    return None
