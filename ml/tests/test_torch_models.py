"""Tiny training runs on synthetic data. Skipped without torch (always on the M1);
run in the CI ML smoke job and on Windows (`uv sync --extra train`)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from vsl_ml import torch_models  # noqa: E402
from vsl_ml.augment import augment  # noqa: E402
from vsl_ml.data import FloatArray, synthetic_examples  # noqa: E402

pytestmark = pytest.mark.train


def _data() -> tuple[list[tuple[FloatArray, int]], list[str]]:
    examples = synthetic_examples(signers=2, takes=3).examples
    names = sorted({e.label for e in examples})
    return [(e.features, names.index(e.label)) for e in examples], names


@pytest.mark.parametrize("arch", torch_models.ARCHS)
def test_learns_synthetic_signs(arch: torch_models.Arch) -> None:
    data, names = _data()
    result = torch_models.train_model(
        arch, data, data[:6], len(names), torch_models.TrainConfig(epochs=60, seed=0), augment
    )
    logits = torch_models.predict_logits(result.model, [s for s, _ in data])

    assert logits.shape == (len(data), len(names))
    assert (logits.argmax(axis=1) == np.array([k for _, k in data])).mean() > 0.8


@pytest.mark.parametrize("arch", torch_models.ARCHS)
def test_padding_does_not_change_the_output(arch: torch_models.Arch) -> None:
    data, names = _data()
    model = torch_models.build_model(arch, data[0][0].shape[1], len(names), [s for s, _ in data])
    model.eval()
    short, long = data[0][0][:12], data[1][0]
    alone = torch_models.predict_logits(model, [short])
    x, lengths = torch_models._batch([short, long])
    with torch.no_grad():
        batched = model(x, lengths).numpy()[:1]

    np.testing.assert_allclose(alone, batched, atol=1e-4)


@pytest.mark.parametrize("arch", torch_models.ARCHS)
def test_onnx_export_matches_torch(arch: torch_models.Arch, tmp_path: Path) -> None:
    pytest.importorskip("onnxruntime")
    data, names = _data()
    model = torch_models.build_model(arch, data[0][0].shape[1], len(names), [s for s, _ in data])
    path = tmp_path / "model.onnx"
    torch_models.export_onnx(model, path, data[0][0].shape[1])
    seqs = [s for s, _ in data[:5]]

    np.testing.assert_allclose(
        torch_models.onnx_logits(path, seqs), torch_models.predict_logits(model, seqs), atol=1e-4
    )
