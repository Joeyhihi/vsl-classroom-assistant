from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable

from vsl_backend.config import Settings
from vsl_backend.recognition.classifiers import MockClassifier, build_classifier

HEAVY_MODULES = ("onnxruntime", "torch", "mediapipe", "faster_whisper", "ctranslate2")


def test_mock_cycle_covers_every_status_deterministically() -> None:
    a, b = MockClassifier(), MockClassifier()

    run_a = [a.classify([]) for _ in range(6)]
    run_b = [b.classify([]) for _ in range(6)]

    assert [d.status for d in run_a] == ["confident", "uncertain", "rejected"] * 2
    assert run_a == run_b
    assert run_a[0].top[0].gloss_id != run_a[3].top[0].gloss_id


def test_mock_scores_are_sorted_probabilities() -> None:
    clf = MockClassifier()
    for _ in range(9):
        scores = [label.score for label in clf.classify([]).top]
        assert scores == sorted(scores, reverse=True)
        assert all(0 <= s <= 1 for s in scores) and sum(scores) <= 1


def test_mock_labels_are_marked_synthetic() -> None:
    assert all(label.gloss_id.startswith("MOCK_") for label in MockClassifier().classify([]).top)


def test_build_classifier_per_mode(settings_factory: Callable[..., Settings]) -> None:
    assert isinstance(build_classifier(settings_factory()), MockClassifier)
    assert build_classifier(settings_factory(model_mode="template")) is None
    assert build_classifier(settings_factory(model_mode="onnx")) is None


def test_mock_app_imports_no_ml_libraries() -> None:
    # Fresh interpreter so other tests' imports cannot hide a regression (ADR-016).
    code = (
        "import sys; from vsl_backend.main import create_app; "
        "from vsl_backend.config import Settings; "
        "create_app(Settings(_env_file=None)); "
        f"print([m for m in {HEAVY_MODULES!r} if m in sys.modules])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()

    assert out == "[]"
