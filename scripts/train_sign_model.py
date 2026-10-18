"""Phase 5: train, compare, calibrate and export the sign model. Windows laptop / CI only.

    uv run --extra train python scripts/train_sign_model.py --model-id vsl-01          # DATA_ROOT
    uv run --extra train python scripts/train_sign_model.py --model-id vsl-01 --select gru
    uv run --extra train python scripts/train_sign_model.py --model-id smoke --synthetic --out <tmp>

Steps (docs/AI_ML_STRATEGY.md §3-§4, §8):
  1. ACCEPTED / RELABELLED samples from the manifest, trimmed by the live segmenter.
  2. Grouped split (signer > session > sample, whatever the data allows) + leakage check.
  3. Each model (template DTW, GRU, TCN): train, fit the temperature and the
     operating point on validation, evaluate on test.
  4. Pick the best on validation (or `--select`), export it with labels,
     calibration and a model card (sha256 of every file), and check ONNX parity.
  5. Write the G5 report (Markdown + JSON) to DATA_ROOT/reports/models/.

Then set VSL_MODEL_MODE=onnx (or template) and VSL_SIGN_MODEL_ID=<id> and start the
backend with `uv run --extra train python scripts/run_backend.py` (keeps onnxruntime).
Never run this on the M1 Mac: it trains models (hardware policy).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from _common import REPO_ROOT
from _dataset import resolve_data_root
from numpy.typing import NDArray

from vsl_backend.inference.onnx_model import OnnxCalibration, load_onnx_model, save_onnx_model
from vsl_backend.inference.template_model import (
    Calibration,
    calibrate,
    load_template_model,
    save_template_model,
)
from vsl_backend.recognition.classifiers import Classifier, OnnxClassifier, TemplateClassifier
from vsl_backend.schemas.recognition import LabelInfo
from vsl_features.decoding import REJECTION_LABELS, DecisionPolicy
from vsl_features.synth import SYNTHETIC_LABELS
from vsl_features.vocabulary import load_vocabulary
from vsl_ml.augment import augment
from vsl_ml.calibration import OperatingPoint, choose_operating_point, fit_temperature, softmax_rows
from vsl_ml.data import (
    REJECTION_TEXT,
    Example,
    LoadedData,
    load_manifest_examples,
    synthetic_examples,
)
from vsl_ml.metrics import Evaluation, evaluate
from vsl_ml.splits import Split, leakage, make_split
from vsl_ml.template import dtw_logits

ALL_ARCHS = ("template", "gru", "tcn")
PARITY_TOLERANCE = 1e-3


@dataclass
class Result:
    arch: str
    temperature: float
    point: OperatingPoint
    val: Evaluation | None
    test: Evaluation
    notes: list[str] = field(default_factory=list)
    model: Any = None  # torch module for gru/tcn


def class_names_of(examples: list[Example]) -> list[str]:
    labels = {e.label for e in examples}
    return sorted(labels - REJECTION_LABELS) + sorted(labels & REJECTION_LABELS)


def label_infos(class_names: list[str], vocabulary_path: Path | None) -> list[LabelInfo]:
    vocabulary = load_vocabulary(vocabulary_path) if vocabulary_path else None
    out = []
    for name in class_names:
        if name in REJECTION_TEXT:
            text, icon = REJECTION_TEXT[name]
        elif vocabulary and (item := vocabulary.get(name)):
            text, icon = item.text_vi, item.icon
        else:
            text, icon = SYNTHETIC_LABELS.get(name, (name, "hand"))
        out.append(LabelInfo(gloss_id=name, text_vi=text, icon=icon))
    return out


def _y(examples: list[Example], index: dict[str, int]) -> NDArray[np.int64]:
    return np.array([index[e.label] for e in examples], dtype=np.int64)


def calibrate_and_evaluate(
    arch: str,
    logits_of: Any,
    split: Split,
    class_names: list[str],
    max_far: float,
    seed: int,
) -> Result:
    """Temperature + operating point on validation (train if no validation), test once."""
    index = {c: k for k, c in enumerate(class_names)}
    notes = []
    fit_on = split.val
    if not fit_on:
        fit_on = split.train
        notes.append("no validation split: calibrated on training data (optimistic)")
    fit_logits = logits_of(fit_on)
    temperature = fit_temperature(fit_logits, _y(fit_on, index))
    fit_probs = softmax_rows(fit_logits, temperature)
    point = choose_operating_point(fit_probs, _y(fit_on, index), class_names, max_far)
    policy = DecisionPolicy(point.threshold, point.margin, point.floor)

    def run(examples: list[Example]) -> Evaluation:
        probs = softmax_rows(logits_of(examples), temperature)
        return evaluate(
            probs, _y(examples, index), class_names, [e.signer_id for e in examples], policy, seed
        )

    val = run(split.val) if split.val else None
    return Result(arch, temperature, point, val, run(split.test), notes)


def train_neural(
    arch: str, split: Split, class_names: list[str], epochs: int, seed: int
) -> tuple[Any, Any, list[str]]:
    from vsl_ml import torch_models

    index = {c: k for k, c in enumerate(class_names)}
    config = torch_models.TrainConfig(epochs=epochs, seed=seed)
    trained = torch_models.train_model(
        arch,  # type: ignore[arg-type]
        [(e.features, index[e.label]) for e in split.train],
        [(e.features, index[e.label]) for e in split.val],
        len(class_names),
        config,
        augment,
    )
    notes = [f"trained {trained.epochs_run} epochs, best at {trained.best_epoch}"]

    def logits_of(examples: list[Example]) -> NDArray[np.float64]:
        return torch_models.predict_logits(trained.model, [e.features for e in examples])

    return trained.model, logits_of, notes


def select(results: list[Result], forced: str | None) -> Result:
    if forced:
        chosen = [r for r in results if r.arch == forced]
        if not chosen:
            sys.exit(f"error: --select {forced} was not trained")
        return chosen[0]

    def score(r: Result) -> tuple[bool, float, float]:
        ev = r.val or r.test  # validation; test only if there is no validation split
        return (r.point.meets_target, ev.macro_f1, r.point.coverage)

    return max(results, key=score)


def export(
    best: Result,
    args: argparse.Namespace,
    split: Split,
    class_names: list[str],
    labels: list[LabelInfo],
    data: LoadedData,
    meta: dict[str, Any],
) -> Path:
    developer_only = bool(meta["developer_only"])
    dataset = {
        "dataset_version": data.fingerprint,
        "split_level": split.level,
        "counts": {
            "train": len(split.train),
            "val": len(split.val),
            "test": len(split.test),
        },
        "signers": len({e.signer_id for e in data.examples}),
    }
    metrics = {
        "arch": best.arch,
        "test": _summary(best.test),
        "operating_point": best.point.to_dict(),
        "temperature": best.temperature,
    }
    if best.arch == "template":
        index = {c: k for k, c in enumerate(class_names)}
        templates = [(index[e.label], e.features) for e in split.train]
        p = best.point
        cal = Calibration(
            temperature=best.temperature,
            max_distance=calibrate(templates).max_distance,
            threshold=p.threshold,
            margin=p.margin,
            floor=p.floor,
        )
        return save_template_model(
            args.out,
            args.model_id,
            labels,
            templates,
            data.extractor_version,
            data.extractor_backend,
            cal,
        )

    from vsl_ml import torch_models

    with tempfile.TemporaryDirectory() as tmp:
        onnx_path = Path(tmp) / "model.onnx"
        torch_models.export_onnx(best.model, onnx_path, split.train[0].features.shape[1])
        seqs = [e.features for e in split.test]
        diff = float(
            np.abs(
                torch_models.onnx_logits(onnx_path, seqs)
                - torch_models.predict_logits(best.model, seqs)
            ).max()
        )
        if diff > PARITY_TOLERANCE:
            sys.exit(f"error: ONNX output differs from torch by {diff:.2e}")
        print(f"ONNX parity OK (max |diff| {diff:.1e})")
        metrics["onnx_parity_max_abs_diff"] = diff
        p = best.point
        return save_onnx_model(
            args.out,
            args.model_id,
            onnx_path,
            labels,
            OnnxCalibration(best.temperature, p.threshold, p.margin, p.floor),
            vocabulary_version=str(meta["vocabulary_version"]),
            extractor_version=data.extractor_version,
            extractor_backend=data.extractor_backend,
            developer_only=developer_only,
            dataset=dataset,
            metrics=metrics,
        )


def verify_load(args: argparse.Namespace, arch: str, test: list[Example]) -> str:
    """Load the artifact exactly as the backend does (sha256 checks) and classify the test set."""
    classifier: Classifier
    if arch == "template":
        classifier = TemplateClassifier(load_template_model(args.out, args.model_id))
    else:
        classifier = OnnxClassifier(load_onnx_model(args.out, args.model_id))
    targets = [e for e in test if e.label not in REJECTION_LABELS]
    hits = 0
    for e in targets:
        decision = classifier.classify(e.features)
        hits += bool(decision.top) and decision.top[0].gloss_id == e.label
    rejected = sum(
        classifier.classify(e.features).status == "rejected"
        for e in test
        if e.label in REJECTION_LABELS
    )
    others = len(test) - len(targets)
    return (
        f"backend load check OK: top-1 right on {hits}/{len(targets)} test signs, "
        f"{rejected}/{others} non-sign or unknown takes rejected"
    )


def _summary(ev: Evaluation) -> dict[str, Any]:
    keys = ("n", "accuracy", "macro_f1", "macro_f1_ci", "top3", "far", "wrong_rate")
    rest = ("coverage", "ece", "min_signer_accuracy")
    return {k: getattr(ev, k) for k in (*keys, *rest)}


def _pct(v: float) -> str:
    return f"{100 * v:.1f}%"


def report_markdown(
    args: argparse.Namespace,
    split: Split,
    data: LoadedData,
    results: list[Result],
    best: Result,
    warnings: list[str],
) -> str:
    counts = {name: len(items) for name, items in (("train", split.train), ("val", split.val))}
    lines = [
        f"# Sign model report: {args.model_id}",
        "",
        f"- Created: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Dataset version (manifest sha256): `{data.fingerprint}`",
        f"- Samples used: {len(data.examples)} from "
        f"{len({e.signer_id for e in data.examples})} signer(s)",
        f"- Split level: **{split.level}** (train {counts['train']}, val {counts['val']}, "
        f"test {len(split.test)})",
        f"- Held-out distractor identities: {', '.join(split.held_out_distractors) or 'none'}",
        f"- Target FAR / confident-wrong limit: {_pct(args.max_far)}",
        "",
    ]
    if warnings:
        lines += ["## Warnings", "", *[f"- {w}" for w in warnings], ""]
    lines += [
        "## Models (test split)",
        "",
        "| Model | Macro-F1 (95% CI) | Top-3 | FAR | Wrong | Coverage | ECE | Min signer |"
        " Operating point |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        t, p = r.test, r.point
        mark = " **(selected)**" if r is best else ""
        lines.append(
            f"| {r.arch}{mark} | {t.macro_f1:.3f} ({t.macro_f1_ci[0]:.2f}-{t.macro_f1_ci[1]:.2f}) "
            f"| {_pct(t.top3)} | {_pct(t.far)} | {_pct(t.wrong_rate)} | {_pct(t.coverage)} "
            f"| {t.ece:.3f} | {_pct(t.min_signer_accuracy)} | τ={p.threshold} m={p.margin} "
            f"T={r.temperature:.2f}{'' if p.meets_target else ' ⚠ target not met'} |"
        )
    lines += [
        "",
        "FAR = non-sign / out-of-vocabulary takes accepted as a confident sign. "
        "Wrong = known signs confidently given the wrong word. "
        "Coverage = known signs confidently given the right word.",
        "",
        f"## Selected: {best.arch}",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|",
    ]
    for name, m in best.test.per_class.items():
        lines.append(
            f"| {name} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} "
            f"| {int(m['support'])} |"
        )
    lines += ["", "Per signer (accuracy on known signs): "]
    lines.append(", ".join(f"{s} {_pct(v)}" for s, v in best.test.per_signer.items()) or "n/a")
    lines += ["", "Confusion matrix (rows = truth):", ""]
    lines.append("| | " + " | ".join(best.test.class_names) + " |")
    lines.append("|---" * (len(best.test.class_names) + 1) + "|")
    for name, row in zip(best.test.class_names, best.test.confusion, strict=True):
        lines.append(f"| {name} | " + " | ".join(str(v) for v in row) + " |")
    for r in results:
        if r.notes:
            lines += ["", f"Notes ({r.arch}): " + "; ".join(r.notes)]
    lines += [
        "",
        "## Gate G5 (owner decision)",
        "",
        "- [ ] Macro-F1 and its confidence interval are acceptable",
        "- [ ] The weakest signer is acceptable",
        "- [ ] FAR on unseen distractors and non-sign motion is acceptable",
        "- [ ] Approve this operating point, **or** pivot: smaller vocabulary, more data, "
        "different features, stop",
    ]
    if split.level != "signer":
        lines += [
            "",
            f"⚠ Split level is `{split.level}`: the test takes come from signers seen in "
            "training, so these numbers are a prototype check, not a G5 result. "
            "G5 needs ≥3 held-out signers (B4).",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--synthetic", action="store_true", help="synthetic signers (CI smoke)")
    parser.add_argument("--data-root", type=Path)
    parser.add_argument(
        "--vocabulary", type=Path, default=REPO_ROOT / "ml" / "vocabulary" / "vocabulary.dev.json"
    )
    parser.add_argument("--archs", default=",".join(ALL_ARCHS), help="comma list of models")
    parser.add_argument("--select", choices=ALL_ARCHS, help="export this model, not the best")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--max-far", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "model-artifacts")
    parser.add_argument("--report-dir", type=Path, help="default: DATA_ROOT/reports/models")
    args = parser.parse_args(argv)

    archs = [a.strip() for a in args.archs.split(",") if a.strip()]
    if unknown := set(archs) - set(ALL_ARCHS):
        parser.error(f"unknown model(s): {sorted(unknown)}")
    warnings: list[str] = []
    if {"gru", "tcn"} & set(archs) and importlib.util.find_spec("torch") is None:
        archs = [a for a in archs if a == "template"]
        warnings.append("torch is not installed (uv run --extra train ...): GRU/TCN skipped")
        print(f"warning: {warnings[-1]}")
        if not archs:
            sys.exit("error: nothing to train without torch")

    if args.synthetic:
        data = synthetic_examples(seed=args.seed)
        vocabulary_path = None
        meta: dict[str, Any] = {"vocabulary_version": "synthetic", "developer_only": True}
        report_dir = args.report_dir or args.out / "reports"
    else:
        data_root = resolve_data_root(args.data_root)
        vocabulary = load_vocabulary(args.vocabulary)
        data = load_manifest_examples(data_root, vocabulary)
        vocabulary_path = args.vocabulary
        meta = {
            "vocabulary_version": vocabulary.version,
            "developer_only": vocabulary.developer_only
            or any(e.signer_id.startswith("DEV-") for e in data.examples),
        }
        report_dir = args.report_dir or data_root / "reports" / "models"
    warnings += data.warnings

    class_names = class_names_of(data.examples)
    if len([c for c in class_names if c not in REJECTION_LABELS]) < 2:
        sys.exit("error: need accepted takes of at least 2 signs (review them in 'Duyệt mẫu')")
    split = make_split(data.examples, seed=args.seed)
    if problems := leakage(split):
        sys.exit("error: split leakage: " + "; ".join(problems))
    if not split.test:
        sys.exit("error: no test samples; record at least 2 takes of every sign")
    missing = set(class_names) - {e.label for e in split.train}
    if missing:
        warnings.append(f"classes with no training sample: {sorted(missing)}")
    if split.level != "signer":
        warnings.append(f"split level '{split.level}': prototype numbers, not a G5 result")
    print(
        f"{len(data.examples)} samples, {len(class_names)} classes, split by {split.level}: "
        f"train {len(split.train)} / val {len(split.val)} / test {len(split.test)}"
    )

    results: list[Result] = []
    for arch in archs:
        print(f"--- {arch}")
        if arch == "template":

            def logits_of(examples: list[Example]) -> NDArray[np.float64]:
                return dtw_logits(split.train, [e.features for e in examples], class_names)

            result = calibrate_and_evaluate(
                arch, logits_of, split, class_names, args.max_far, args.seed
            )
        else:
            model, neural_logits, notes = train_neural(
                arch, split, class_names, args.epochs, args.seed
            )
            result = calibrate_and_evaluate(
                arch, neural_logits, split, class_names, args.max_far, args.seed
            )
            result.model = model
            result.notes = notes + result.notes
        t = result.test
        print(
            f"test macro-F1 {t.macro_f1:.3f}, FAR {_pct(t.far)}, coverage {_pct(t.coverage)}"
            + ("" if result.point.meets_target else " (operating-point target not met)")
        )
        results.append(result)

    best = select(results, args.select)
    labels = label_infos(class_names, vocabulary_path)
    directory = export(best, args, split, class_names, labels, data, meta)
    print(verify_load(args, best.arch, split.test))

    report_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.model_id}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    (report_dir / f"{stem}.md").write_text(
        report_markdown(args, split, data, results, best, warnings), encoding="utf-8"
    )
    (report_dir / f"{stem}.json").write_text(
        json.dumps(
            {
                "model_id": args.model_id,
                "selected": best.arch,
                "split_level": split.level,
                "warnings": warnings,
                "results": [
                    {
                        "arch": r.arch,
                        "temperature": r.temperature,
                        "operating_point": r.point.to_dict(),
                        "val": r.val.to_dict() if r.val else None,
                        "test": r.test.to_dict(),
                    }
                    for r in results
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    mode = "template" if best.arch == "template" else "onnx"
    print(f"selected {best.arch}; wrote {directory}")
    print(f"report: {report_dir / (stem + '.md')}")
    print(f"use: VSL_MODEL_MODE={mode} VSL_SIGN_MODEL_ID={args.model_id}")
    if mode == "onnx":
        print("start: uv run --extra train python scripts/run_backend.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
