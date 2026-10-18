"""Build a developer template model from recorder exports (Phase 3 walking skeleton).

    uv run python scripts/build_templates.py --model-id dev-templates-01 rec1.json rec2.json
    uv run python scripts/build_templates.py --model-id synthetic-demo --synthetic

Input: files saved by the in-app recorder (format "vsl-recording-v1"), containing
**the developer's own signs only**. Each take is trimmed with the same utterance
segmenter used live. Output goes to model-artifacts/sign/<model-id>/ (gitignored).
Then set VSL_MODEL_MODE=template and VSL_SIGN_MODEL_ID=<model-id>.

`--synthetic` builds a demo model from the synthetic signer (tests/demos only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from _common import REPO_ROOT

from vsl_backend.inference.template_model import FloatArray, save_template_model
from vsl_backend.schemas.recognition import LabelInfo
from vsl_features import FEATURE_SPEC
from vsl_features.frames import Frame, FrameError, parse_frame
from vsl_features.normalize import sequence_features
from vsl_features.segmentation import UtteranceSegmenter
from vsl_features.synth import IMAGE_HEIGHT, IMAGE_WIDTH, SYNTHETIC_LABELS, Variation, synth_sign

MIN_FRAMES = 5


def trim(frames: list[Frame], aspect: float) -> list[Frame]:
    """Keep the first utterance found in a take; fall back to the whole take."""
    segmenter = UtteranceSegmenter(aspect)
    for frame in frames:
        if (utterance := segmenter.push(frame)) is not None:
            return utterance.frames
    return frames


def from_recordings(paths: list[Path]) -> tuple[list[LabelInfo], list[tuple[int, FloatArray]], str]:
    labels: list[LabelInfo] = []
    index: dict[str, int] = {}
    templates: list[tuple[int, FloatArray]] = []
    extractor = "unknown"
    for path in paths:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != "vsl-recording-v1":
            sys.exit(f"error: {path} is not a vsl-recording-v1 file")
        if data.get("feature_spec_version") != FEATURE_SPEC.version:
            sys.exit(f"error: {path} uses feature spec {data.get('feature_spec_version')}")
        extractor = str(data.get("extractor", {}).get("version", "unknown"))
        aspect = data["image_width"] / data["image_height"]
        gloss = str(data["label"]["gloss_id"])
        if gloss not in index:
            index[gloss] = len(labels)
            labels.append(LabelInfo.model_validate(data["label"]))
        for take in data["takes"]:
            frames = []
            for raw in take["frames"]:
                try:
                    frames.append(parse_frame(raw))
                except FrameError:
                    continue
            seq = sequence_features(trim(frames, aspect), aspect)
            if len(seq) >= MIN_FRAMES:
                templates.append((index[gloss], seq))
            else:
                print(f"warning: skipped a take of {gloss} in {path.name} (too few usable frames)")
    return labels, templates, extractor


def synthetic(takes: int, seed: int) -> tuple[list[LabelInfo], list[tuple[int, FloatArray]]]:
    rng = np.random.default_rng(seed)
    aspect = IMAGE_WIDTH / IMAGE_HEIGHT
    labels = [LabelInfo(gloss_id=g, text_vi=t, icon=i) for g, (t, i) in SYNTHETIC_LABELS.items()]
    templates = []
    for k, label in enumerate(labels):
        for _ in range(takes):
            frames = synth_sign(label.gloss_id, 0.0, 15.0, rng, Variation.random(rng))
            templates.append((k, sequence_features(trim(frames, aspect), aspect)))
    return labels, templates


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("recordings", nargs="*", type=Path)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--synthetic", action="store_true", help="demo model from synthetic data")
    parser.add_argument("--takes", type=int, default=3, help="synthetic takes per label")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "model-artifacts")
    args = parser.parse_args()

    if args.synthetic:
        labels, templates = synthetic(args.takes, args.seed)
        extractor, backend = "synthetic", "synthetic"
    else:
        if not args.recordings:
            parser.error("give recorder files, or --synthetic")
        labels, templates, extractor = from_recordings(args.recordings)
        backend = "browser"
    if not templates:
        sys.exit("error: no usable takes")
    directory = save_template_model(args.out, args.model_id, labels, templates, extractor, backend)
    print(f"wrote {len(templates)} templates for {len(labels)} labels to {directory}")
    print(f"use: VSL_MODEL_MODE=template VSL_SIGN_MODEL_ID={args.model_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
