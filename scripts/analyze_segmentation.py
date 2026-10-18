"""Analyse recorder takes to tune the utterance segmenter on real landmarks.

    uv run python scripts/analyze_segmentation.py ~/vsl-data/recordings/p3-segmentation/
    uv run python scripts/analyze_segmentation.py rec1.json rec2.json --json report.json

Input: "vsl-recording-v1" files from the in-app recorder (the developer's own
takes; keep them OUTSIDE the repo). Label convention:
    REST_*   hands at rest (desk, lap, lowered)      → must NOT start a unit
    HOLD     hands raised and held still              → must count as "still"
    anything else is a sign take: rest → sign → rest  → must start a unit

Reports, per take and per group: wrist height (shoulder widths below the
shoulder midpoint, y down), wrist speed (raw and smoothed, shoulder widths/s),
and what the current segmenter does. Then suggests thresholds that separate rest
and hold jitter from signing. Needs no camera or model; prints no landmark values.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from vsl_features.frames import Frame, FrameError, parse_frame
from vsl_features.normalize import body_frame
from vsl_features.segmentation import SegmenterConfig, UtteranceSegmenter, Wrists, wrist_speed

CONFIG = SegmenterConfig()  # thresholds currently in use
GROUPS = ("rest", "hold", "sign")


def group_of(gloss_id: str) -> str:
    if gloss_id.upper().startswith("REST"):
        return "rest"
    if gloss_id.upper().startswith("HOLD"):
        return "hold"
    return "sign"


def _pct(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


@dataclass
class TakeStats:
    file: str
    gloss_id: str
    group: str
    take: int
    frames: int
    dropped: int
    fps: float | None
    hands_visible_pct: float
    shoulders_ok_pct: float
    wrist_y_p05: float | None  # highest hand position (small y = high)
    wrist_y_p50: float | None
    speed_raw_p50: float | None
    speed_raw_p95: float | None
    speed_smooth_p50: float | None
    speed_smooth_p95: float | None
    segmenter_started: bool
    segmenter_closes: list[str] = field(default_factory=list)
    segmenter_state_at_end: str = ""


def _speeds(
    frames: list[Frame], aspect: float
) -> tuple[list[float], list[float], list[float], int]:
    """Wrist heights (all visible hands), raw and smoothed speed of ACTIVE wrists only
    (above the rest line - what the segmenter reacts to), and the shoulder-ok count.

    Hands at rest or flickering at the frame edge are below the rest line, so their
    jumps no longer count as "motion" (this produced a false NOT SEPARABLE before).
    """
    heights: list[float] = []
    raw: list[float] = []
    smooth: list[float] = []
    ok = 0
    prev: tuple[float, Wrists] | None = None
    ema: float | None = None
    for frame in frames:
        body = body_frame(frame, aspect)
        if body is None:
            prev = None
            continue
        ok += 1
        visible = {
            s: w
            for s, w in (("left", body.left_wrist), ("right", body.right_wrist))
            if w is not None
        }
        heights += [float(w[1]) for w in visible.values()]
        wrists = {s: w for s, w in visible.items() if w[1] < CONFIG.rest_line}
        if prev is not None and wrists.keys() & prev[1].keys():
            dt = (frame.t_ms - prev[0]) / 1000.0
            if dt > 0:
                speed = wrist_speed(prev, frame.t_ms, wrists)
                raw.append(speed)
                alpha = 1.0 - math.exp(-dt * 1000.0 / CONFIG.speed_smoothing_ms)
                ema = speed if ema is None else ema + alpha * (speed - ema)
                smooth.append(ema)
        prev = (frame.t_ms, wrists)
    return heights, raw, smooth, ok


def analyse_take(path: Path, data: dict[str, Any], index: int, raw_frames: list[Any]) -> TakeStats:
    aspect = data["image_width"] / data["image_height"]
    frames: list[Frame] = []
    dropped = 0
    for raw in raw_frames:
        try:
            frames.append(parse_frame(raw))
        except FrameError:
            dropped += 1
    frames.sort(key=lambda f: f.t_ms)
    heights, raw_speed, smooth_speed, shoulders_ok = _speeds(frames, aspect)

    segmenter = UtteranceSegmenter(aspect)
    started = False
    closes: list[str] = []
    for frame in frames:
        utterance = segmenter.push(frame)
        started = started or segmenter.state == "signing" or utterance is not None
        if utterance is not None:
            closes.append(utterance.reason)

    span = (frames[-1].t_ms - frames[0].t_ms) / 1000.0 if len(frames) > 1 else 0.0
    n = max(len(frames), 1)
    gloss = str(data["label"]["gloss_id"])
    return TakeStats(
        file=path.name,
        gloss_id=gloss,
        group=group_of(gloss),
        take=index,
        frames=len(frames),
        dropped=dropped,
        fps=round((len(frames) - 1) / span, 1) if span > 0 else None,
        hands_visible_pct=round(100 * sum(f.hands_visible for f in frames) / n, 1),
        shoulders_ok_pct=round(100 * shoulders_ok / n, 1),
        wrist_y_p05=_pct(heights, 5),
        wrist_y_p50=_pct(heights, 50),
        speed_raw_p50=_pct(raw_speed, 50),
        speed_raw_p95=_pct(raw_speed, 95),
        speed_smooth_p50=_pct(smooth_speed, 50),
        speed_smooth_p95=_pct(smooth_speed, 95),
        segmenter_started=started,
        segmenter_closes=closes,
        segmenter_state_at_end=segmenter.state,
    )


def load_takes(paths: list[Path]) -> list[TakeStats]:
    files: list[Path] = []
    for p in paths:
        files += sorted(p.expanduser().glob("*.json")) if p.is_dir() else [p.expanduser()]
    takes: list[TakeStats] = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != "vsl-recording-v1":
            print(f"skip {path.name}: not a vsl-recording-v1 file", file=sys.stderr)
            continue
        for i, take in enumerate(data["takes"], start=1):
            takes.append(analyse_take(path, data, i, take["frames"]))
    return takes


@dataclass
class Suggestion:
    name: str
    current: float
    suggested: float | None
    separable: bool
    reason: str


def suggest(takes: list[TakeStats]) -> list[Suggestion]:
    cfg = CONFIG

    def values(group: str, attr: str) -> list[float]:
        return [v for t in takes if t.group == group and (v := getattr(t, attr)) is not None]

    still_jitter = values("rest", "speed_smooth_p95") + values("hold", "speed_smooth_p95")
    sign_motion = values("sign", "speed_smooth_p95")
    rest_heights = values("rest", "wrist_y_p05")  # highest rest hand
    sign_heights = values("sign", "wrist_y_p05")  # highest signing hand
    out: list[Suggestion] = []

    if still_jitter and sign_motion:
        jitter, motion = max(still_jitter), min(sign_motion)
        ok = jitter < motion
        middle = (jitter + motion) / 2
        detail = f"max rest/hold jitter p95 {jitter:.3f} vs min sign p95 {motion:.3f}"
        # "still" sits just above jitter; "start" halfway between jitter and signing motion.
        still = round(min(jitter * 1.25, middle), 3) if ok else None
        start = round(middle, 3) if ok else None
        out.append(Suggestion("still_speed (smoothed)", cfg.still_speed, still, ok, detail))
        out.append(Suggestion("start_speed (smoothed)", cfg.start_speed, start, ok, detail))
    if rest_heights and sign_heights:
        lowest_sign, highest_rest = max(sign_heights), min(rest_heights)
        ok = lowest_sign < highest_rest
        out.append(
            Suggestion(
                "rest_line",
                cfg.rest_line,
                round((lowest_sign + highest_rest) / 2, 2) if ok else None,
                ok,
                f"signing reaches y<={lowest_sign:.2f}; rest stays y>={highest_rest:.2f}",
            )
        )
    return out


def _fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:.2f}"


def print_report(takes: list[TakeStats], suggestions: list[Suggestion]) -> None:
    print(f"{len(takes)} takes\n")
    header = (
        f"{'label':<12}{'#':>3}{'fps':>6}{'hands%':>8}{'y p05':>7}{'y p50':>7}"
        f"{'v raw p95':>11}{'v smooth p50/p95':>18}  segmenter"
    )
    print(header)
    print("-" * len(header))
    for t in takes:
        seg = ("started" if t.segmenter_started else "idle") + (
            f", closed: {','.join(t.segmenter_closes)}" if t.segmenter_closes else ""
        )
        print(
            f"{t.gloss_id:<12}{t.take:>3}{_fmt(t.fps):>6}{t.hands_visible_pct:>8.0f}"
            f"{_fmt(t.wrist_y_p05):>7}{_fmt(t.wrist_y_p50):>7}{_fmt(t.speed_raw_p95):>11}"
            f"{_fmt(t.speed_smooth_p50):>9}/{_fmt(t.speed_smooth_p95):<8}  {seg}"
        )
    print(
        f"\nCurrent: rest_line {CONFIG.rest_line}, start {CONFIG.start_speed}, "
        f"still {CONFIG.still_speed}."
    )
    print(
        "Speeds count only wrists above the rest line. Expected: REST_*/HOLD idle, signs started."
    )
    false_starts = [t for t in takes if t.group == "rest" and t.segmenter_started]
    missed = [t for t in takes if t.group == "sign" and not t.segmenter_started]
    print(
        f"false starts on rest takes: {len(false_starts)}; "
        f"sign takes never started: {len(missed)}\n"
    )
    print("Suggested thresholds (units: shoulder widths, shoulder widths/s):")
    for s in suggestions:
        verdict = f"{s.suggested}" if s.separable else "NOT SEPARABLE"
        print(f"  {s.name:<24} current {s.current:<6} → {verdict:<14} ({s.reason})")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("paths", nargs="+", type=Path, help="recording files or folders")
    parser.add_argument("--json", type=Path, help="also write the full report as JSON")
    args = parser.parse_args()
    takes = load_takes(args.paths)
    if not takes:
        sys.exit("error: no vsl-recording-v1 takes found")
    suggestions = suggest(takes)
    print_report(takes, suggestions)
    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "takes": [asdict(t) for t in takes],
                    "suggestions": [asdict(s) for s in suggestions],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
