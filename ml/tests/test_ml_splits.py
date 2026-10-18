from __future__ import annotations

import numpy as np
import pytest

from vsl_ml.data import DISTRACTOR, Example, synthetic_examples
from vsl_ml.splits import Split, choose_level, leakage, make_split

SEQ = np.zeros((6, 3), dtype=np.float32)


def ex(i: int, signer: str, session: str, label: str = "A", kind: str = "target") -> Example:
    source = label
    return Example(
        sample_id=f"{session}-{i:03d}",
        signer_id=signer,
        session_id=session,
        label=DISTRACTOR if kind == "distractor" else label,
        source_label=source,
        kind=kind,  # type: ignore[arg-type]
        features=SEQ,
    )


def test_level_is_the_strongest_the_data_allows() -> None:
    signers = [ex(i, f"SGN-0{i}", f"S{i}") for i in range(3)]
    sessions = [ex(i, "DEV-01", f"S{i}") for i in range(3)]
    one_session = [ex(i, "DEV-01", "S0") for i in range(6)]

    assert choose_level(signers) == "signer"
    assert choose_level(sessions) == "session"
    assert choose_level(one_session) == "sample"


def test_signer_split_holds_out_whole_signers() -> None:
    data = synthetic_examples(signers=6, takes=2)
    split = make_split(data.examples, seed=1)

    assert split.level == "signer"
    assert leakage(split) == []
    test_signers = {e.signer_id for e in split.test}
    assert len(test_signers) == 3  # ≥3 held-out signers when there are enough
    assert not test_signers & {e.signer_id for e in split.train + split.val}
    assert split.train and split.val


def test_sample_split_keeps_every_class_in_training() -> None:
    data = [ex(i, "DEV-01", "S0", label) for i, label in enumerate("AAAABBBBBC")]
    split = make_split(data, seed=0)

    assert split.level == "sample"
    assert {e.label for e in split.train} == {"A", "B", "C"}
    assert split.test and leakage(split) == []


def test_distractor_identities_in_test_are_unseen() -> None:
    data = []
    for s in range(5):
        for k, gloss in enumerate(("DST_01", "DST_02", "DST_03")):
            data.append(ex(10 * s + k, f"SGN-0{s}", f"S{s}", gloss, "distractor"))
        data.append(ex(10 * s + 5, f"SGN-0{s}", f"S{s}", "A"))
    split = make_split(data, seed=3)

    assert len(split.held_out_distractors) == 1
    test_ids = {e.source_label for e in split.test if e.kind == "distractor"}
    assert test_ids <= set(split.held_out_distractors)
    assert leakage(split) == []


def test_leakage_is_detected() -> None:
    a, b = ex(1, "SGN-01", "S1"), ex(2, "SGN-01", "S1")
    assert leakage(Split("signer", [a], [], [b])) == ["signer groups in both train and test: 1"]


def test_empty_input_is_an_error() -> None:
    with pytest.raises(ValueError):
        make_split([])
