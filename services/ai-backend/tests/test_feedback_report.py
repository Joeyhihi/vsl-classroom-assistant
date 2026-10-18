from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT
from vsl_backend.feedback_store import FeedbackStore

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import feedback_report


def row(verdict: str, predicted: str = "DEV_01", expected: str | None = None) -> dict[str, object]:
    return {
        "session_id": "s1",
        "prediction_id": "p",
        "model_id": "vsl-01",
        "predicted_gloss_id": predicted,
        "confidence": 0.8 if verdict == "correct" else 0.6,
        "verdict": verdict,
        "expected_gloss_id": expected,
    }


def test_report_counts_shares_and_confusions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = FeedbackStore(tmp_path)
    for r in [row("correct")] * 3 + [row("incorrect", expected="DEV_02")] * 2 + [row("unsure")]:
        store.append(r)
    with store.path.open("a", encoding="utf-8") as handle:
        handle.write("not json\n")

    assert feedback_report.main(["--data-root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "| vsl-01 | 6 | 3 | 2 | 1 | 60%" in out
    assert "| DEV_01 | DEV_02 | 2 |" in out
    assert "1 unreadable skipped" in out
    assert len(list((tmp_path / "reports").glob("feedback-*.md"))) == 1


def test_empty_feedback(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert feedback_report.main(["--data-root", str(tmp_path), "--no-save"]) == 0
    assert "No feedback yet." in capsys.readouterr().out


def test_wilson_interval() -> None:
    lo, hi = feedback_report.wilson(8, 10)
    assert 0.44 < lo < 0.5 and 0.94 < hi < 0.97
    assert feedback_report.wilson(0, 0) == (0.0, 0.0)
