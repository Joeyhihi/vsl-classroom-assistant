"""Vocabulary files (JSON). Phase 4 uses a developer-only placeholder vocabulary;
the expert-validated vocabulary (B1) will use the same item fields."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vsl_features.dataset import LABEL, SAMPLE_KINDS, DatasetError, SampleKind


@dataclass(frozen=True)
class VocabularyItem:
    gloss_id: str
    text_vi: str
    icon: str
    sample_kind: SampleKind


@dataclass(frozen=True)
class Vocabulary:
    version: str
    developer_only: bool
    items: tuple[VocabularyItem, ...]

    def get(self, gloss_id: str) -> VocabularyItem | None:
        return next((i for i in self.items if i.gloss_id == gloss_id), None)


def load_vocabulary(path: Path) -> Vocabulary:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise DatasetError(f"cannot read vocabulary {path.name}") from None
    items = []
    for raw in data.get("items", []):
        gloss = str(raw.get("gloss_id", ""))
        kind = raw.get("sample_kind")
        if not LABEL.fullmatch(gloss) or kind not in SAMPLE_KINDS:
            raise DatasetError(f"invalid vocabulary item {gloss!r}")
        text = str(raw.get("text_vi", "")).strip()
        if not text:
            raise DatasetError(f"vocabulary item {gloss} has no text_vi")
        items.append(
            VocabularyItem(gloss, text.replace("\r", ""), str(raw.get("icon", "hand")), kind)
        )
    if len({i.gloss_id for i in items}) != len(items):
        raise DatasetError("duplicate gloss_id in vocabulary")
    if not items:
        raise DatasetError("vocabulary has no items")
    return Vocabulary(
        str(data.get("vocabulary_version", "")), bool(data.get("developer_only")), tuple(items)
    )
