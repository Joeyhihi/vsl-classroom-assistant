"""scripts/analyze_segmentation.py on synthetic recorder files (no real data)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from tests.conftest import REPO_ROOT
from vsl_features.frames import Frame, frame_to_wire
from vsl_features.synth import IMAGE_HEIGHT, IMAGE_WIDTH, Variation, synth_rest, synth_sign

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import analyze_segmentation as analysis


def write_recording(path: Path, gloss_id: str, takes: list[list[Frame]]) -> None:
    path.write_text(
        json.dumps(
            {
                "format": "vsl-recording-v1",
                "developer_own_data": True,
                "feature_spec_version": "fs-1",
                "extractor": {"version": "synthetic", "backend": "synthetic"},
                "image_width": IMAGE_WIDTH,
                "image_height": IMAGE_HEIGHT,
                "label": {"gloss_id": gloss_id, "text_vi": gloss_id, "icon": "x"},
                "takes": [{"frames": [frame_to_wire(f) for f in take]} for take in takes],
                "created_at": "2026-10-18T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )


def hold_take(rng: np.random.Generator) -> list[Frame]:
    """Hand raised in front of the chest, held still with tracker-like jitter."""
    raised = synth_sign("SYN_A", 0, 15, rng)[8]
    assert raised.right_hand is not None
    frames = []
    for i in range(45):
        hand = raised.right_hand + rng.normal(0, 0.002, raised.right_hand.shape).astype(np.float32)
        frames.append(Frame(i * 66.7, raised.pose, raised.left_hand, hand, raised.face))
    return frames


def sign_take(label: str, rng: np.random.Generator) -> list[Frame]:
    frames = synth_rest(0, 400, 15, rng)
    frames += synth_sign(label, frames[-1].t_ms + 66.7, 15, rng, Variation.random(rng))
    return frames + synth_rest(frames[-1].t_ms + 66.7, 400, 15, rng)


def recordings(tmp_path: Path) -> Path:
    rng = np.random.default_rng(3)
    write_recording(
        tmp_path / "rest.json", "REST_DESK", [synth_rest(0, 3000, 15, rng) for _ in range(3)]
    )
    write_recording(tmp_path / "hold.json", "HOLD", [hold_take(rng) for _ in range(3)])
    for label in ("SYN_A", "SYN_B"):
        write_recording(
            tmp_path / f"{label}.json", label, [sign_take(label, rng) for _ in range(3)]
        )
    (tmp_path / "package.json").write_text('{"name": "not a recording"}', encoding="utf-8")
    return tmp_path


def test_groups_and_segmenter_behaviour(tmp_path: Path) -> None:
    takes = analysis.load_takes([recordings(tmp_path)])

    assert {t.group for t in takes} == {"rest", "hold", "sign"}
    assert len(takes) == 12  # package.json is skipped
    assert not any(t.segmenter_started for t in takes if t.group == "rest")
    assert all(t.segmenter_started for t in takes if t.group == "sign")
    assert all(t.fps and 14 < t.fps < 16 for t in takes)


def test_suggestions_separate_rest_from_signing(tmp_path: Path) -> None:
    suggestions = {s.name: s for s in analysis.suggest(analysis.load_takes([recordings(tmp_path)]))}

    assert all(s.separable for s in suggestions.values())
    still = suggestions["still_speed (smoothed)"].suggested
    start = suggestions["start_speed (smoothed)"].suggested
    assert still is not None and start is not None and still < start
    assert suggestions["rest_line"].suggested is not None


def test_report_runs_and_writes_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "in").mkdir()
    folder = recordings(tmp_path / "in")
    out = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["analyze_segmentation.py", str(folder), "--json", str(out)])
    assert analysis.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert len(report["takes"]) == 12 and len(report["suggestions"]) == 3
