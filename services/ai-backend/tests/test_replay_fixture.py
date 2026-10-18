from __future__ import annotations

import sys

import numpy as np

from tests.conftest import REPO_ROOT, load_replay

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from gen_synthetic_replay import build


def test_committed_replay_matches_the_generator() -> None:
    """Numeric comparison: libm differences across OSes may change the last digit."""
    committed, fresh = load_replay(), build()

    assert {k: v for k, v in committed.items() if k != "frames"} == {
        k: v for k, v in fresh.items() if k != "frames"
    }
    assert len(committed["frames"]) == len(fresh["frames"])
    for a, b in zip(committed["frames"], fresh["frames"], strict=True):
        for key in ("pose", "left_hand", "right_hand", "face"):
            assert (a[key] is None) == (b[key] is None)
            if a[key] is not None:
                np.testing.assert_allclose(a[key], b[key], atol=2e-4)


def test_replay_is_marked_synthetic() -> None:
    replay = load_replay()
    assert replay["synthetic"] is True and replay["format"] == "vsl-replay-v1"
    assert all(s["label"].startswith("SYN_") for s in replay["segments"])
