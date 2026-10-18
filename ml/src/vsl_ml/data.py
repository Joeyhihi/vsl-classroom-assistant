"""Training examples from the reviewed manifest in DATA_ROOT, or from the synthetic signer.

Only ACCEPTED or RELABELLED samples are used. Each take is trimmed with the same
utterance segmenter as live recognition, so training sees what serving sees.
Distractor samples become `__distractor__` and background samples
`__background__` (docs/AI_ML_STRATEGY.md §2, unknown rejection).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from vsl_features.dataset import Dataset, SampleKind, load_frames
from vsl_features.decoding import REJECTION_LABELS
from vsl_features.frames import Frame
from vsl_features.normalize import sequence_features
from vsl_features.segmentation import UtteranceSegmenter
from vsl_features.synth import IMAGE_HEIGHT, IMAGE_WIDTH, Variation, synth_rest, synth_sign
from vsl_features.vocabulary import Vocabulary

FloatArray = NDArray[np.float32]

BACKGROUND = "__background__"
DISTRACTOR = "__distractor__"
assert {BACKGROUND, DISTRACTOR} == REJECTION_LABELS
MIN_FRAMES = 5

REJECTION_TEXT = {
    BACKGROUND: ("Không phải ký hiệu", "rest"),
    DISTRACTOR: ("Ký hiệu ngoài từ vựng", "question"),
}


@dataclass(frozen=True)
class Example:
    sample_id: str
    signer_id: str
    session_id: str
    label: str  # class: a target gloss_id, __distractor__ or __background__
    source_label: str  # the recorded gloss (distractor identity)
    kind: SampleKind
    features: FloatArray = field(repr=False)


@dataclass(frozen=True)
class LoadedData:
    examples: list[Example]
    warnings: list[str]
    fingerprint: str  # sha256 over the manifest files (dataset version)
    extractor_version: str
    extractor_backend: str


def class_of(label: str, kind: SampleKind) -> str:
    if kind == "distractor":
        return DISTRACTOR
    if kind == "background":
        return BACKGROUND
    return label


def first_utterance(frames: list[Frame], aspect: float) -> list[Frame]:
    """The first utterance the live segmenter finds; the whole take if none (rest takes)."""
    segmenter = UtteranceSegmenter(aspect)
    for frame in frames:
        if (utterance := segmenter.push(frame)) is not None:
            return utterance.frames
    return frames


def manifest_fingerprint(dataset: Dataset) -> str:
    digest = hashlib.sha256()
    for name in ("samples.jsonl", "reviews.jsonl", "tombstones.jsonl"):
        path = dataset.manifests / name
        digest.update(name.encode())
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def load_manifest_examples(data_root: Path, vocabulary: Vocabulary) -> LoadedData:
    dataset = Dataset(data_root)
    examples: list[Example] = []
    warnings: list[str] = []
    extractors: Counter[tuple[str, str]] = Counter()
    for view in dataset.samples():
        if not view.usable:
            continue
        record = view.record
        item = vocabulary.get(view.label)
        if item is None:
            warnings.append(f"{record.sample_id}: label {view.label} is not in the vocabulary")
            continue
        aspect = record.image_w / record.image_h
        seq = sequence_features(
            first_utterance(load_frames(dataset.path_of(record)), aspect), aspect
        )
        if len(seq) < MIN_FRAMES:
            warnings.append(f"{record.sample_id}: too few usable frames")
            continue
        examples.append(
            Example(
                sample_id=record.sample_id,
                signer_id=record.signer_id,
                session_id=record.session_id,
                label=class_of(item.gloss_id, item.sample_kind),
                source_label=item.gloss_id,
                kind=item.sample_kind,
                features=seq,
            )
        )
        extractors[(record.extractor_version, record.extractor_backend)] += 1
    version, backend = extractors.most_common(1)[0][0] if extractors else ("unknown", "unknown")
    if len(extractors) > 1:
        warnings.append(f"mixed extractors: {sorted(extractors)}")
    return LoadedData(examples, warnings, manifest_fingerprint(dataset), version, backend)


SYNTHETIC_TARGETS = ("SYN_A", "SYN_B")
SYNTHETIC_DISTRACTOR = "SYN_C"


def synthetic_examples(signers: int = 5, takes: int = 4, seed: int = 0) -> LoadedData:
    """Made-up motion patterns (not VSL) for tests and the CI smoke job.

    SYN_A and SYN_B are targets, SYN_C plays an out-of-vocabulary distractor and
    resting hands are background.
    """
    rng = np.random.default_rng(seed)
    aspect = IMAGE_WIDTH / IMAGE_HEIGHT
    examples: list[Example] = []
    plan: list[tuple[str, SampleKind]] = [(g, "target") for g in SYNTHETIC_TARGETS]
    plan += [(SYNTHETIC_DISTRACTOR, "distractor"), ("REST_DESK", "background")]
    for s in range(signers):
        signer, session = f"SYN-{s + 1:02d}", f"S20260101-0000{s:02d}-0000"
        for gloss, kind in plan:
            for _ in range(takes):
                if kind == "background":
                    frames = synth_rest(0.0, 1500.0, 15.0, rng)
                else:
                    frames = synth_sign(gloss, 0.0, 15.0, rng, Variation.random(rng))
                seq = sequence_features(first_utterance(frames, aspect), aspect)
                examples.append(
                    Example(
                        sample_id=f"{session}-{len(examples) + 1:03d}",
                        signer_id=signer,
                        session_id=session,
                        label=class_of(gloss, kind),
                        source_label=gloss,
                        kind=kind,
                        features=seq,
                    )
                )
    return LoadedData(examples, [], "synthetic", "synthetic", "synthetic")
