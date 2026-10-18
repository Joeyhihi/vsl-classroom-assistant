"""Phase 7 gate G7 measurements: WER, latency and RSS for ≥2 STT model sizes. Windows only.

    uv run --extra stt python scripts/benchmark_stt.py --models base,small
    uv run --extra stt python scripts/benchmark_stt.py --models small --device cuda --compute int8

Test set (consented recordings only, outside the repo):
    DATA_ROOT/stt_testset/<name>.wav   16 kHz mono 16-bit PCM, ≤ 30 s
    DATA_ROOT/stt_testset/<name>.txt   the reference transcript (Vietnamese)

Writes DATA_ROOT/reports/stt/stt-<time>.md. The report has scores and timings only,
never transcripts. Never run this on the M1 Mac (models are downloaded and run).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import psutil
from _common import REPO_ROOT
from _dataset import resolve_data_root
from numpy.typing import NDArray

from vsl_backend.stt.audio import SAMPLE_RATE, AudioError, parse_wav
from vsl_backend.stt.engine import SttEngine, TranscriberFactory

MAX_AUDIO_S = 30.0


def normalize_text(text: str) -> list[str]:
    """NFC, lower case, punctuation removed (Vietnamese diacritics kept), split on spaces."""
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def word_errors(reference: list[str], hypothesis: list[str]) -> int:
    """Levenshtein distance over words (substitutions + insertions + deletions)."""
    previous = list(range(len(hypothesis) + 1))
    for i, ref_word in enumerate(reference, start=1):
        current = [i]
        for j, hyp_word in enumerate(hypothesis, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (ref_word != hyp_word),
                )
            )
        previous = current
    return previous[-1]


@dataclass(frozen=True)
class Clip:
    name: str
    audio: NDArray[np.float32]
    reference: list[str]

    @property
    def seconds(self) -> float:
        return len(self.audio) / SAMPLE_RATE


def load_testset(folder: Path) -> tuple[list[Clip], list[str]]:
    clips: list[Clip] = []
    problems: list[str] = []
    for wav in sorted(folder.glob("*.wav")):
        ref = wav.with_suffix(".txt")
        if not ref.is_file():
            problems.append(f"{wav.name}: no reference .txt")
            continue
        try:
            audio = parse_wav(wav.read_bytes(), MAX_AUDIO_S)
        except AudioError as exc:
            problems.append(f"{wav.name}: {exc}")
            continue
        clips.append(Clip(wav.stem, audio, normalize_text(ref.read_text(encoding="utf-8"))))
    return clips, problems


@dataclass(frozen=True)
class ModelResult:
    model: str
    device: str
    load_s: float
    wer: float
    latency_p50_ms: float
    latency_p95_ms: float
    real_time_factor: float  # processing time / audio time
    rss_peak_mb: float
    fell_back_to_cpu: bool


def benchmark(
    model: str,
    device: str,
    compute: str,
    clips: list[Clip],
    download_root: Path,
    factory: TranscriberFactory | None = None,
    rss_mb: Callable[[], float] = lambda: psutil.Process().memory_info().rss / 2**20,
) -> ModelResult:
    kwargs = {"factory": factory} if factory else {}
    engine = SttEngine(model, device, compute, download_root, **kwargs)
    start = time.perf_counter()
    engine.load()
    load_s = time.perf_counter() - start
    peak = rss_mb()
    errors = words = 0
    latencies: list[float] = []
    audio_s = 0.0
    for clip in clips:
        t0 = time.perf_counter()
        segments = engine.transcribe(clip.audio, "vi")
        latencies.append((time.perf_counter() - t0) * 1000)
        peak = max(peak, rss_mb())
        hypothesis = normalize_text(" ".join(s.text for s in segments))
        errors += word_errors(clip.reference, hypothesis)
        words += len(clip.reference)
        audio_s += clip.seconds
    engine.unload()
    return ModelResult(
        model=model,
        device=engine.device,
        load_s=round(load_s, 2),
        wer=errors / words if words else 0.0,
        latency_p50_ms=float(np.percentile(latencies, 50)) if latencies else 0.0,
        latency_p95_ms=float(np.percentile(latencies, 95)) if latencies else 0.0,
        real_time_factor=(sum(latencies) / 1000) / audio_s if audio_s else 0.0,
        rss_peak_mb=round(peak, 1),
        fell_back_to_cpu=engine.fell_back_to_cpu,
    )


def report(results: list[ModelResult], clips: list[Clip], problems: list[str], compute: str) -> str:
    total = sum(c.seconds for c in clips)
    lines = [
        "# STT benchmark (gate G7)",
        "",
        f"- Created: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Clips: {len(clips)} ({total:.0f} s of audio, "
        f"{sum(len(c.reference) for c in clips)} reference words)",
        f"- Compute type: {compute}",
        "",
        "| Model | Device | Load | WER | Latency p50 / p95 | Real-time factor | Peak RSS |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        device = f"{r.device}{' (OOM fallback)' if r.fell_back_to_cpu else ''}"
        lines.append(
            f"| {r.model} | {device} | {r.load_s:.1f} s | {100 * r.wer:.1f}% "
            f"| {r.latency_p50_ms:.0f} / {r.latency_p95_ms:.0f} ms | {r.real_time_factor:.2f} "
            f"| {r.rss_peak_mb:.0f} MB |"
        )
    lines += [
        "",
        "Real-time factor < 1 means faster than speaking. Measure with Chrome and MediaPipe "
        "running, as in class.",
        "",
        "## Gate G7 (owner decision)",
        "",
        "- [ ] WER is good enough for classroom subtitles",
        "- [ ] Latency after releasing the button is acceptable",
        "- [ ] RSS leaves enough memory for Chrome + MediaPipe",
        "- [ ] Approve STT with model ___, **or** defer it",
    ]
    if problems:
        lines += ["", "## Skipped files", "", *[f"- {p}" for p in problems]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--models", default="base,small", help="comma list (≥2 for G7)")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute", default="int8")
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--testset", type=Path, help="default: DATA_ROOT/stt_testset")
    parser.add_argument("--download-root", type=Path, default=REPO_ROOT / "model-artifacts" / "stt")
    args = parser.parse_args(argv)

    data_root = resolve_data_root(args.data_root)
    folder = args.testset or data_root / "stt_testset"
    clips, problems = load_testset(folder)
    for p in problems:
        print(f"warning: {p}")
    if not clips:
        sys.exit(f"error: no usable .wav + .txt pairs in {folder}")

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    results = []
    for model in models:
        print(f"--- {model} on {args.device}/{args.compute}")
        result = benchmark(model, args.device, args.compute, clips, args.download_root)
        print(
            f"WER {100 * result.wer:.1f}%, p95 {result.latency_p95_ms:.0f} ms, "
            f"RTF {result.real_time_factor:.2f}, RSS {result.rss_peak_mb:.0f} MB"
        )
        results.append(result)

    out = data_root / "reports" / "stt"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"stt-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.md"
    path.write_text(report(results, clips, problems, args.compute), encoding="utf-8")
    print(f"report: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
