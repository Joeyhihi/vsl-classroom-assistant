"""Quality report for the recorded dataset (aggregates only, no landmark values).

    uv run python scripts/dataset_report.py                 # print + save to DATA_ROOT/reports/
    uv run python scripts/dataset_report.py --no-save

Per label: sample kind, counts by review status, duration, fps, dropped frames,
how often pose/hands were tracked, and what the utterance segmenter does with
the take. Also integrity problems (missing files, sha256 mismatches).
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from _dataset import resolve_data_root

from vsl_features.dataset import Dataset, SampleView, load_frames
from vsl_features.segmentation import UtteranceSegmenter

REVIEW_ORDER = ("pending", "accepted", "rejected", "relabelled")
COLUMNS = (
    "Label",
    "Kind",
    "n",
    "acc / rej / pend",
    "Duration s",
    "fps",
    "Dropped %",
    "Pose %",
    "Hands %",
    "Segmenter started",
    "Closes",
)


@dataclass
class LabelStats:
    kind: str
    statuses: Counter[str] = field(default_factory=Counter)
    durations_s: list[float] = field(default_factory=list)
    fps: list[float] = field(default_factory=list)
    dropped_pct: list[float] = field(default_factory=list)
    pose_pct: list[float] = field(default_factory=list)
    hands_pct: list[float] = field(default_factory=list)
    started: int = 0
    closes: Counter[str] = field(default_factory=Counter)


def analyse(dataset: Dataset, view: SampleView, stats: LabelStats) -> None:
    record = view.record
    frames = load_frames(dataset.path_of(record))
    n = max(len(frames), 1)
    stats.statuses[view.status] += 1
    stats.durations_s.append((frames[-1].t_ms - frames[0].t_ms) / 1000 if len(frames) > 1 else 0.0)
    stats.fps.append(record.fps)
    stats.dropped_pct.append(
        100 * record.dropped_frames / (record.n_frames + record.dropped_frames)
    )
    stats.pose_pct.append(100 * sum(f.pose is not None for f in frames) / n)
    stats.hands_pct.append(100 * sum(f.hands_visible for f in frames) / n)
    segmenter = UtteranceSegmenter(record.image_w / record.image_h)
    started = False
    for frame in frames:
        utterance = segmenter.push(frame)
        started = started or segmenter.state == "signing" or utterance is not None
        if utterance is not None:
            stats.closes[utterance.reason] += 1
    stats.started += started


def mean(values: list[float]) -> str:
    return f"{statistics.fmean(values):.1f}" if values else "-"


def render(dataset: Dataset) -> str:
    views = dataset.samples()
    by_label: dict[str, LabelStats] = {}
    signers: Counter[str] = Counter()
    sessions: set[str] = set()
    for view in views:
        stats = by_label.setdefault(view.label, LabelStats(kind=view.record.sample_kind))
        analyse(dataset, view, stats)
        signers[view.record.signer_id] += 1
        sessions.add(view.record.session_id)
    statuses: Counter[str] = Counter(v.status for v in views)
    problems = dataset.verify()
    lines = [
        f"# Dataset quality report — {datetime.now(UTC).isoformat(timespec='seconds')}",
        "",
        f"- Samples: **{len(views)}** in {len(sessions)} session(s); deleted (tombstoned): "
        f"{len(dataset.tombstoned())}",
        "- Review: " + ", ".join(f"{k} {statuses[k]}" for k in REVIEW_ORDER),
        f"- Signers: {', '.join(f'{s} ({n})' for s, n in sorted(signers.items())) or '-'}",
        "- Inter-annotator agreement: N/A (single reviewer in self-recording)",
        f"- Integrity: {'OK' if not problems else f'{len(problems)} problem(s)'}",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "---|" * len(COLUMNS),
    ]
    for label in sorted(by_label):
        s = by_label[label]
        n = sum(s.statuses.values())
        closes = ", ".join(f"{k} {v}" for k, v in sorted(s.closes.items())) or "-"
        usable = s.statuses["accepted"] + s.statuses["relabelled"]
        cells = [
            label,
            s.kind,
            str(n),
            f"{usable} / {s.statuses['rejected']} / {s.statuses['pending']}",
            mean(s.durations_s),
            mean(s.fps),
            mean(s.dropped_pct),
            mean(s.pose_pct),
            mean(s.hands_pct),
            f"{s.started}/{n}",
            closes,
        ]
        lines.append("| " + " | ".join(cells) + " |")
    warnings = []
    for label, s in sorted(by_label.items()):
        n = sum(s.statuses.values())
        if s.kind == "background" and s.started:
            warnings.append(
                f"- {label}: the segmenter started on {s.started}/{n} rest takes (false starts)."
            )
        if s.kind in ("target", "distractor") and s.started < n:
            warnings.append(f"- {label}: {n - s.started}/{n} sign takes never started.")
        if s.pose_pct and statistics.fmean(s.pose_pct) < 80:
            warnings.append(f"- {label}: pose tracked in only {mean(s.pose_pct)}% of frames.")
    if warnings or problems:
        lines += ["", "## Warnings", "", *warnings, *(f"- {p}" for p in problems)]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--no-save", action="store_true", help="print only")
    args = parser.parse_args(argv)
    root = resolve_data_root(args.data_root)
    report = render(Dataset(root))
    print(report)
    if not args.no_save:
        out = root / "reports" / f"quality-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
