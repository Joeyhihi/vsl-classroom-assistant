"""Summarise prediction feedback (P9 feedback analysis): DATA_ROOT/feedback/feedback.jsonl.

    uv run python scripts/feedback_report.py               # print + save to DATA_ROOT/reports/
    uv run python scripts/feedback_report.py --no-save

Per model: verdict counts, the share marked correct (with a 95% Wilson interval),
mean confidence by verdict, and the most common "predicted X, meant Y" confusions.
Feedback holds IDs and verdicts only, so the report contains no personal data.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from _dataset import resolve_data_root

VERDICTS = ("correct", "incorrect", "unsure")


def load_rows(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Valid rows and the number of unreadable lines."""
    rows: list[dict[str, Any]] = []
    bad = 0
    if not path.is_file():
        return rows, bad
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(row, dict) and row.get("verdict") in VERDICTS and row.get("model_id"):
            rows.append(row)
        else:
            bad += 1
    return rows, bad


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def report(rows: list[dict[str, Any]], bad: int) -> str:
    lines = [
        "# Feedback report",
        "",
        f"- Created: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Feedback rows: {len(rows)}" + (f" ({bad} unreadable skipped)" if bad else ""),
        f"- Sessions: {len({r.get('session_id') for r in rows})}",
        "",
    ]
    if not rows:
        return "\n".join([*lines, "No feedback yet."]) + "\n"
    by_model: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_model[str(r["model_id"])].append(r)

    lines += [
        "| Model | n | Correct | Incorrect | Unsure | Correct share (95% CI) | Mean conf. ✓ / ✗ |",
        "|---|---|---|---|---|---|---|",
    ]
    for model, items in sorted(by_model.items()):
        counts = Counter(r["verdict"] for r in items)
        decided = counts["correct"] + counts["incorrect"]
        lo, hi = wilson(counts["correct"], decided)
        share = f"{100 * counts['correct'] / decided:.0f}% ({100 * lo:.0f}-{100 * hi:.0f}%)"

        def mean_conf(verdict: str, items: list[dict[str, Any]] = items) -> str:
            values = [float(r.get("confidence", 0)) for r in items if r["verdict"] == verdict]
            return f"{sum(values) / len(values):.2f}" if values else "-"

        lines.append(
            f"| {model} | {len(items)} | {counts['correct']} | {counts['incorrect']} "
            f"| {counts['unsure']} | {share if decided else '-'} "
            f"| {mean_conf('correct')} / {mean_conf('incorrect')} |"
        )

    confusions = Counter(
        (str(r.get("predicted_gloss_id")), str(r.get("expected_gloss_id") or "?"))
        for r in rows
        if r["verdict"] == "incorrect"
    )
    lines += ["", "## Most common confusions (predicted → meant)", ""]
    if confusions:
        lines += ["| Predicted | Meant | Count |", "|---|---|---|"]
        for (predicted, meant), n in confusions.most_common(10):
            lines.append(f"| {predicted} | {meant} | {n} |")
        lines += ["", '"?" = the user said it was wrong but did not pick the intended sign.']
    else:
        lines.append("None.")
    lines += [
        "",
        "Feedback is self-reported and only covers confirmed predictions, so it measures "
        "the confirm step, not raw model accuracy. Use the P5 report for model metrics.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args(argv)

    root = resolve_data_root(args.data_root)
    rows, bad = load_rows(root / "feedback" / "feedback.jsonl")
    text = report(rows, bad)
    print(text)
    if not args.no_save:
        out = root / "reports"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"feedback-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.md"
        path.write_text(text, encoding="utf-8")
        print(f"saved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
