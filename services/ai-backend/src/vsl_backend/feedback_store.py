"""Local prediction feedback (FR-13): `DATA_ROOT/feedback/feedback.jsonl`.

Append-only while in use, deleted in one action (`DELETE /api/v1/feedback`,
"Xoá dữ liệu cục bộ"). Rows hold IDs, a confidence and a verdict, never free
text, and are never logged (docs/SECURITY_AND_PRIVACY.md).
"""

from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from vsl_features.dataset import DatasetError, ensure_outside_repo, now_iso


class FeedbackStore:
    def __init__(self, data_root: Path) -> None:
        self.root = data_root
        self.path = data_root / "feedback" / "feedback.jsonl"
        self._lock = threading.Lock()

    def append(self, row: dict[str, Any]) -> str:
        """Write one row and return its new feedback_id. Raises DatasetError for a bad root."""
        ensure_outside_repo(self.root)
        feedback_id = uuid.uuid4().hex
        line = json.dumps(
            {"feedback_id": feedback_id, "at": now_iso(), **row},
            ensure_ascii=False,
            sort_keys=True,
        )
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return feedback_id

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def delete_all(self) -> bool:
        """Remove every feedback row. Returns False if there was nothing to delete."""
        with self._lock:
            if not self.path.exists():
                return False
            self.path.unlink()
            return True


__all__ = ["DatasetError", "FeedbackStore"]
