"""benchmark_stt.py helpers with a fake transcriber (no model on the M1)."""

from __future__ import annotations

import sys
from pathlib import Path

from tests.conftest import REPO_ROOT
from tests.test_stt import FakeTranscriber, wav_bytes

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import benchmark_stt


def test_normalize_keeps_vietnamese_diacritics() -> None:
    assert benchmark_stt.normalize_text("Xin chào, CÁC em!") == ["xin", "chào", "các", "em"]


def test_word_errors() -> None:
    ref = ["xin", "chào", "các", "em"]
    assert benchmark_stt.word_errors(ref, ref) == 0
    assert benchmark_stt.word_errors(ref, ["xin", "chào", "em"]) == 1  # deletion
    # one substitution + one insertion
    assert benchmark_stt.word_errors(ref, ["xin", "chao", "các", "em", "nhé"]) == 2
    assert benchmark_stt.word_errors([], ["a"]) == 1


def test_benchmark_and_report_on_a_fake_model(tmp_path: Path) -> None:
    folder = tmp_path / "stt_testset"
    folder.mkdir()
    (folder / "a.wav").write_bytes(wav_bytes(1.0))
    (folder / "a.txt").write_text("Xin chào các bạn", encoding="utf-8")
    (folder / "b.wav").write_bytes(wav_bytes(1.0))  # no reference
    (folder / "c.wav").write_bytes(wav_bytes(1.0, rate=8000))
    (folder / "c.txt").write_text("x", encoding="utf-8")

    clips, problems = benchmark_stt.load_testset(folder)
    assert [c.name for c in clips] == ["a"] and len(problems) == 2

    result = benchmark_stt.benchmark(
        "small",
        "cpu",
        "int8",
        clips,
        tmp_path / "models",
        factory=lambda *args: FakeTranscriber(),
        rss_mb=lambda: 512.0,
    )
    assert result.wer == 0.25  # "bạn" → "em"
    assert result.rss_peak_mb == 512.0 and not result.fell_back_to_cpu

    text = benchmark_stt.report([result], clips, problems, "int8")
    assert "| small | cpu |" in text and "25.0%" in text and "Gate G7" in text
    assert "Xin chào" not in text  # no transcripts in the report
