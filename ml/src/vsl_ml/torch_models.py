"""GRU and TCN sequence classifiers, training loop and ONNX export.

Needs the `train` extra (CPU torch). Imported only by the training script and
the torch tests, which skip when torch is missing (the M1 never installs it).

Both models normalise their input inside the graph (train-set mean/std), so the
backend feeds `vsl_features.normalize.sequence_features` output unchanged. At
inference there is one utterance and no padding: `forward(x)` with no lengths,
which is also the graph that is exported.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import torch
from numpy.typing import NDArray
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

from vsl_ml.data import FloatArray

Arch = Literal["gru", "tcn"]
ARCHS: tuple[Arch, ...] = ("gru", "tcn")
ONNX_OPSET = 17


def _stats(seqs: list[FloatArray]) -> tuple[torch.Tensor, torch.Tensor]:
    frames = np.concatenate(seqs).astype(np.float64)
    mean, std = frames.mean(axis=0), frames.std(axis=0)
    std = np.where(std < 1e-3, 1.0, std)
    return torch.tensor(mean, dtype=torch.float32), torch.tensor(std, dtype=torch.float32)


def _mask(lengths: torch.Tensor, steps: int) -> torch.Tensor:
    return (torch.arange(steps)[None, :] < lengths[:, None]).float()


class GRUClassifier(nn.Module):
    """Bidirectional 2x128 GRU, masked mean pooling (the recommended baseline)."""

    def __init__(
        self,
        dim: int,
        n_classes: int,
        mean: torch.Tensor,
        std: torch.Tensor,
        hidden: int = 128,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()
        self.register_buffer("mean", mean)
        self.register_buffer("std", std)
        self.gru = nn.GRU(
            dim, hidden, num_layers=2, batch_first=True, bidirectional=True, dropout=dropout
        )
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(2 * hidden, n_classes)

    def forward(self, x: torch.Tensor, lengths: torch.Tensor | None = None) -> torch.Tensor:
        x = (x - self.mean) / self.std
        if lengths is None:
            out, _ = self.gru(x)
            pooled = out.mean(dim=1)
        else:
            packed = pack_padded_sequence(x, lengths, batch_first=True, enforce_sorted=False)
            out, _ = self.gru(packed)
            out, _ = pad_packed_sequence(out, batch_first=True, total_length=x.shape[1])
            mask = _mask(lengths, x.shape[1]).unsqueeze(-1)
            pooled = (out * mask).sum(dim=1) / lengths[:, None].float()
        return self.head(self.dropout(pooled))


class _TCNBlock(nn.Module):
    def __init__(self, c_in: int, c_out: int, dilation: int, dropout: float) -> None:
        super().__init__()
        self.conv = nn.Conv1d(c_in, c_out, kernel_size=5, dilation=dilation, padding=2 * dilation)
        self.res = nn.Conv1d(c_in, c_out, kernel_size=1) if c_in != c_out else nn.Identity()
        self.dropout = nn.Dropout(dropout)

    def forward(self, h: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        # Re-masking after every block makes padded training batches see exactly
        # the zeros that convolution padding gives a single unpadded utterance.
        return (self.dropout(torch.relu(self.conv(h))) + self.res(h)) * mask


class TCNClassifier(nn.Module):
    """Dilated 1D convolutions (1, 2, 4; receptive field 25 frames), masked mean pooling."""

    def __init__(
        self,
        dim: int,
        n_classes: int,
        mean: torch.Tensor,
        std: torch.Tensor,
        channels: int = 128,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()
        self.register_buffer("mean", mean)
        self.register_buffer("std", std)
        self.blocks = nn.ModuleList(
            [
                _TCNBlock(dim if i == 0 else channels, channels, d, dropout)
                for i, d in enumerate((1, 2, 4))
            ]
        )
        self.head = nn.Linear(channels, n_classes)

    def forward(self, x: torch.Tensor, lengths: torch.Tensor | None = None) -> torch.Tensor:
        x = (x - self.mean) / self.std
        h = x.transpose(1, 2)
        if lengths is None:
            mask = torch.ones_like(h[:, :1, :])
        else:
            mask = _mask(lengths, x.shape[1]).unsqueeze(1)
        h = h * mask
        for block in self.blocks:
            h = block(h, mask)
        pooled = h.sum(dim=2) / mask.sum(dim=2)
        return self.head(pooled)


def build_model(arch: Arch, dim: int, n_classes: int, seqs: list[FloatArray]) -> nn.Module:
    mean, std = _stats(seqs)
    if arch == "gru":
        return GRUClassifier(dim, n_classes, mean, std)
    return TCNClassifier(dim, n_classes, mean, std)


@dataclass(frozen=True)
class TrainConfig:
    epochs: int = 150
    batch_size: int = 16
    lr: float = 1e-3
    weight_decay: float = 1e-2
    patience: int = 25
    seed: int = 0


@dataclass(frozen=True)
class TrainResult:
    model: nn.Module
    epochs_run: int
    best_epoch: int
    best_val_loss: float | None


def _batch(seqs: list[FloatArray]) -> tuple[torch.Tensor, torch.Tensor]:
    lengths = torch.tensor([len(s) for s in seqs], dtype=torch.int64)
    x = torch.zeros(len(seqs), int(lengths.max()), seqs[0].shape[1])
    for i, s in enumerate(seqs):
        x[i, : len(s)] = torch.from_numpy(s)
    return x, lengths


def _loss(
    model: nn.Module,
    seqs: list[FloatArray],
    y: list[int],
    loss_fn: nn.Module,
) -> float:
    model.eval()
    with torch.no_grad():
        x, lengths = _batch(seqs)
        return float(loss_fn(model(x, lengths), torch.tensor(y)))


def train_model(
    arch: Arch,
    train: list[tuple[FloatArray, int]],
    val: list[tuple[FloatArray, int]],
    n_classes: int,
    config: TrainConfig,
    augment: Callable[[FloatArray, np.random.Generator], FloatArray],
) -> TrainResult:
    """Class-balanced cross-entropy, AdamW, early stopping on validation loss."""
    torch.manual_seed(config.seed)
    rng = np.random.default_rng(config.seed)
    seqs = [s for s, _ in train]
    labels = np.array([k for _, k in train])
    model = build_model(arch, seqs[0].shape[1], n_classes, seqs)
    counts = np.bincount(labels, minlength=n_classes).astype(np.float64)
    weights = np.where(counts > 0, len(labels) / (n_classes * np.maximum(counts, 1)), 0.0)
    loss_fn = nn.CrossEntropyLoss(weight=torch.tensor(weights, dtype=torch.float32))
    optimiser = torch.optim.AdamW(
        model.parameters(), lr=config.lr, weight_decay=config.weight_decay
    )

    best_state, best_loss, best_epoch, epoch = copy.deepcopy(model.state_dict()), None, 0, 0
    for epoch in range(1, config.epochs + 1):
        model.train()
        order = rng.permutation(len(train))
        for start in range(0, len(train), config.batch_size):
            idx = order[start : start + config.batch_size]
            x, lengths = _batch([augment(seqs[i], rng) for i in idx])
            optimiser.zero_grad()
            loss = loss_fn(model(x, lengths), torch.tensor(labels[idx]))
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimiser.step()
        if val:
            current = _loss(model, [s for s, _ in val], [k for _, k in val], loss_fn)
            if best_loss is None or current < best_loss:
                best_state, best_loss, best_epoch = (
                    copy.deepcopy(model.state_dict()),
                    current,
                    epoch,
                )
            elif epoch - best_epoch >= config.patience:
                break
    if val:
        model.load_state_dict(best_state)
    else:
        best_epoch = epoch
    model.eval()
    return TrainResult(model, epoch, best_epoch, best_loss)


def predict_logits(model: nn.Module, seqs: list[FloatArray]) -> NDArray[np.float64]:
    """One utterance at a time, unpadded: exactly what serving does."""
    model.eval()
    rows = []
    with torch.no_grad():
        for s in seqs:
            rows.append(model(torch.from_numpy(s)[None]).numpy()[0])
    return np.asarray(rows, dtype=np.float64)


def export_onnx(model: nn.Module, path: Path, dim: int) -> None:
    """Input `features` (1, time, dim) float32 → output `logits` (1, classes)."""
    model.eval()
    dummy = torch.zeros(1, 24, dim)
    torch.onnx.export(
        model,
        (dummy,),
        str(path),
        input_names=["features"],
        output_names=["logits"],
        dynamic_axes={"features": {0: "batch", 1: "time"}, "logits": {0: "batch"}},
        opset_version=ONNX_OPSET,
        dynamo=False,
    )


def onnx_logits(path: Path, seqs: list[FloatArray]) -> NDArray[np.float64]:
    import onnxruntime as ort

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    rows = [session.run(None, {"features": s[None].astype(np.float32)})[0][0] for s in seqs]
    return np.asarray(rows, dtype=np.float64)
