"""Generate the synthetic replay fixture used by replay mode, e2e and backend tests.

    uv run python scripts/gen_synthetic_replay.py [--check]

Output: apps/web/public/replay/synthetic-replay-v1.json. Fully synthetic (no real
person); deterministic, so `--check` can verify the committed file is current.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from _common import REPO_ROOT

from vsl_features import FEATURE_SPEC
from vsl_features.frames import frame_to_wire
from vsl_features.synth import IMAGE_HEIGHT, IMAGE_WIDTH, SYNTHETIC_LABELS, synth_session

OUTPUT = REPO_ROOT / "apps" / "web" / "public" / "replay" / "synthetic-replay-v1.json"
FPS = 15.0
SEED = 2026
LABELS = ["SYN_A", "SYN_B", "SYN_C"]


def build() -> dict[str, Any]:
    frames, truth = synth_session(LABELS, fps=FPS, seed=SEED)
    return {
        "format": "vsl-replay-v1",
        "synthetic": True,
        "note": "Synthetic landmarks from vsl_features.synth; not a real person, not VSL signs.",
        "feature_spec_version": FEATURE_SPEC.version,
        "fps": FPS,
        "image_width": IMAGE_WIDTH,
        "image_height": IMAGE_HEIGHT,
        "labels": {k: {"text_vi": v[0], "icon": v[1]} for k, v in SYNTHETIC_LABELS.items()},
        "segments": [{"label": lbl, "start_ms": s, "end_ms": e} for lbl, s, e in truth],
        "frames": [frame_to_wire(f, decimals=4) for f in frames],
    }


def render() -> str:
    return json.dumps(build(), ensure_ascii=False, separators=(",", ":")) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed file differs")
    args = parser.parse_args()
    content = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print(f"{OUTPUT.relative_to(REPO_ROOT)} is stale; run scripts/gen_synthetic_replay.py")
            return 1
        print("synthetic replay: up to date")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)} ({len(content) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
