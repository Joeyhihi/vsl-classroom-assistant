from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from vsl_backend.config import Settings
from vsl_backend.inference.template_model import save_template_model
from vsl_backend.main import create_app
from vsl_backend.schemas.recognition import LabelInfo
from vsl_features.normalize import sequence_features
from vsl_features.synth import IMAGE_HEIGHT, IMAGE_WIDTH, SYNTHETIC_LABELS, Variation, synth_sign

ALLOWED_ORIGIN = "http://localhost:5173"
REPO_ROOT = Path(__file__).resolve().parents[3]
REPLAY_PATH = REPO_ROOT / "apps" / "web" / "public" / "replay" / "synthetic-replay-v1.json"
SYNTHETIC_MODEL_ID = "synthetic-test"


def make_settings(**overrides: Any) -> Settings:
    # _env_file=None: tests never read the developer's .env.
    return Settings(_env_file=None, **overrides)


@pytest.fixture
def settings_factory() -> Callable[..., Settings]:
    return make_settings


@pytest.fixture
def client_factory() -> Callable[..., TestClient]:
    def factory(**overrides: Any) -> TestClient:
        return TestClient(create_app(make_settings(**overrides)), raise_server_exceptions=False)

    return factory


@pytest.fixture
def client(client_factory: Callable[..., TestClient]) -> TestClient:
    return client_factory()


# --- synthetic data (public repo: no real landmarks) ---------------------------


def load_replay() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="session")
def replay() -> dict[str, Any]:
    return load_replay()


def build_synthetic_model(artifacts_dir: Path, model_id: str = SYNTHETIC_MODEL_ID) -> Path:
    rng = np.random.default_rng(11)
    aspect = IMAGE_WIDTH / IMAGE_HEIGHT
    labels = [LabelInfo(gloss_id=g, text_vi=t, icon=i) for g, (t, i) in SYNTHETIC_LABELS.items()]
    templates = [
        (
            k,
            sequence_features(
                synth_sign(label.gloss_id, 0, 15, rng, Variation.random(rng)), aspect
            ),
        )
        for k, label in enumerate(labels)
        for _ in range(3)
    ]
    return save_template_model(artifacts_dir, model_id, labels, templates, "synthetic", "synthetic")


@pytest.fixture
def artifacts_dir(tmp_path: Path) -> Path:
    build_synthetic_model(tmp_path)
    return tmp_path
