"""Grouped train / validation / test splits (docs/AI_ML_STRATEGY.md §4).

The grouping level is the strongest the data allows:

- `signer`  (≥3 signers): the real protocol; test signers are never seen in training.
- `session` (≥3 sessions): one signer recorded on different days; optimistic.
- `sample`  (otherwise): takes from the same session in train and test; a
  pipeline check only, the numbers say little about new conditions.

Distractor *identities* are split too when there are ≥2 of them, so the test
distractors are signs the model has never seen.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import numpy as np

from vsl_ml.data import Example

SplitLevel = Literal["signer", "session", "sample"]

MIN_GROUPS = 3


@dataclass(frozen=True)
class Split:
    level: SplitLevel
    train: list[Example]
    val: list[Example]
    test: list[Example]
    held_out_distractors: tuple[str, ...] = ()


def _key(level: SplitLevel) -> Callable[[Example], str]:
    if level == "signer":
        return lambda e: e.signer_id
    if level == "session":
        return lambda e: e.session_id
    return lambda e: e.sample_id


def choose_level(examples: list[Example]) -> SplitLevel:
    if len({e.signer_id for e in examples}) >= MIN_GROUPS:
        return "signer"
    if len({e.session_id for e in examples}) >= MIN_GROUPS:
        return "session"
    return "sample"


def _group_counts(n: int, test_fraction: float, min_test: int) -> tuple[int, int]:
    """(test groups, val groups) out of n ≥ 3, leaving at least one for training.

    `min_test` held-out groups only when ≥2 training groups and 1 validation group remain.
    """
    n_test = max(1, round(n * test_fraction))
    if n - min_test >= 3:
        n_test = max(n_test, min_test)
    n_test = min(n_test, n - 2)
    n_val = max(1, round(n * 0.15))
    n_val = min(n_val, n - n_test - 1)
    return n_test, n_val


def _split_groups(
    examples: list[Example],
    level: SplitLevel,
    rng: np.random.Generator,
    test_fraction: float,
    min_test_groups: int,
) -> tuple[list[Example], list[Example], list[Example]]:
    key = _key(level)
    groups = sorted({key(e) for e in examples})
    order = [groups[i] for i in rng.permutation(len(groups))]
    n_test, n_val = _group_counts(len(groups), test_fraction, min_test_groups)
    test_g, val_g = set(order[:n_test]), set(order[n_test : n_test + n_val])
    train = [e for e in examples if key(e) not in test_g | val_g]
    val = [e for e in examples if key(e) in val_g]
    test = [e for e in examples if key(e) in test_g]
    return train, val, test


def _split_samples(
    examples: list[Example], rng: np.random.Generator, test_fraction: float
) -> tuple[list[Example], list[Example], list[Example]]:
    """Stratified per class: every class keeps at least one training example."""
    by_class: dict[str, list[Example]] = defaultdict(list)
    for e in examples:
        by_class[e.label].append(e)
    train: list[Example] = []
    val: list[Example] = []
    test: list[Example] = []
    for label in sorted(by_class):
        items = [by_class[label][i] for i in rng.permutation(len(by_class[label]))]
        n = len(items)
        n_test = 0 if n < 2 else max(1, round(n * test_fraction))
        n_val = 0 if n - n_test < 3 else max(1, round(n * 0.15))
        test += items[:n_test]
        val += items[n_test : n_test + n_val]
        train += items[n_test + n_val :]
    return train, val, test


def make_split(
    examples: list[Example],
    seed: int = 0,
    test_fraction: float = 0.2,
    min_test_groups: int = 3,
    level: SplitLevel | None = None,
) -> Split:
    if not examples:
        raise ValueError("no examples")
    rng = np.random.default_rng(seed)
    level = level or choose_level(examples)
    if level == "sample":
        train, val, test = _split_samples(examples, rng, test_fraction)
    else:
        train, val, test = _split_groups(examples, level, rng, test_fraction, min_test_groups)

    identities = sorted({e.source_label for e in examples if e.kind == "distractor"})
    held_out: tuple[str, ...] = ()
    if len(identities) >= 2:
        n_held = max(1, math.ceil(len(identities) / 3))
        held_out = tuple(sorted(identities[i] for i in rng.permutation(len(identities))[:n_held]))
        seen = set(identities) - set(held_out)

        def keep(e: Example, allowed: set[str]) -> bool:
            return e.kind != "distractor" or e.source_label in allowed

        train = [e for e in train if keep(e, seen)]
        val = [e for e in val if keep(e, seen)]
        test = [e for e in test if keep(e, set(held_out))]
    return Split(level, train, val, test, held_out)


def leakage(split: Split) -> list[str]:
    """Problems that would make the test numbers dishonest. Empty list = clean."""
    problems: list[str] = []
    key = _key(split.level)
    parts = {"train": split.train, "val": split.val, "test": split.test}
    groups = {name: {key(e) for e in items} for name, items in parts.items()}
    for a, b in (("train", "test"), ("val", "test"), ("train", "val")):
        if overlap := groups[a] & groups[b]:
            problems.append(f"{split.level} groups in both {a} and {b}: {len(overlap)}")
    ids = [e.sample_id for items in parts.values() for e in items]
    if len(ids) != len(set(ids)):
        problems.append("a sample appears in more than one split")
    seen = {e.source_label for e in split.train + split.val if e.kind == "distractor"}
    if leaked := seen & set(split.held_out_distractors):
        problems.append(f"held-out distractors seen in training: {sorted(leaked)}")
    return problems
