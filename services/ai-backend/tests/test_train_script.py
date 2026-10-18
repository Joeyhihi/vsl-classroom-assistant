"""train_sign_model.py with the template model only (no torch; synthetic data only).

The GRU/TCN paths run in the CI ML smoke job (`uv sync --extra train`)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT
from tests.test_dataset_scripts import accept_all_but_one, build_dataset
from vsl_backend.inference.template_model import load_template_model
from vsl_backend.recognition.classifiers import TemplateClassifier

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import train_sign_model


def test_synthetic_template_run_writes_model_and_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "artifacts"
    code = train_sign_model.main(
        ["--model-id", "tpl", "--synthetic", "--archs", "template", "--out", str(out)]
    )
    assert code == 0
    stdout = capsys.readouterr().out
    assert "split by signer" in stdout and "VSL_MODEL_MODE=template" in stdout

    model = load_template_model(out, "tpl")
    assert {label.gloss_id for label in model.labels} >= {"SYN_A", "SYN_B", "__background__"}
    classifier = TemplateClassifier(model)
    assert {label.gloss_id for label in classifier.labels} == {"SYN_A", "SYN_B"}

    report = next((out / "reports").glob("tpl-*.md")).read_text(encoding="utf-8")
    assert "Split level: **signer**" in report and "Gate G5" in report
    assert "template **(selected)**" in report
    summary = json.loads(next((out / "reports").glob("tpl-*.json")).read_text(encoding="utf-8"))
    assert summary["selected"] == "template" and summary["results"][0]["test"]["n"] > 0


def test_manifest_run_uses_reviewed_samples_and_warns_on_weak_split(tmp_path: Path) -> None:
    data = tmp_path / "data"
    accept_all_but_one(build_dataset(data))
    out = tmp_path / "artifacts"
    code = train_sign_model.main(
        ["--model-id", "dev", "--archs", "template", "--data-root", str(data), "--out", str(out)]
    )
    assert code == 0

    report = next((data / "reports" / "models").glob("dev-*.md")).read_text(encoding="utf-8")
    assert "prototype numbers, not a G5 result" in report  # 2 signers: no signer split
    model = load_template_model(out, "dev")
    assert model.card.developer_only and model.card.distribution == "private"


def test_neural_models_without_torch_are_skipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    with pytest.raises(SystemExit, match="nothing to train without torch"):
        train_sign_model.main(["--model-id", "x", "--synthetic", "--archs", "gru"])
