from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import SYNTHETIC_MODEL_ID


def test_mock_vocabulary_and_model(client: TestClient) -> None:
    vocab = client.get("/api/v1/vocabulary").json()
    assert vocab["vocabulary_version"] == "mock"
    assert [e["gloss_id"] for e in vocab["entries"]] == ["MOCK_0001", "MOCK_0002", "MOCK_0003"]
    assert client.get("/api/v1/models").json()["kind"] == "mock"


def test_template_vocabulary(
    client_factory: Callable[..., TestClient], artifacts_dir: Path
) -> None:
    client = client_factory(
        model_mode="template", sign_model_id=SYNTHETIC_MODEL_ID, model_artifacts_dir=artifacts_dir
    )
    model = client.get("/api/v1/models").json()
    assert model == {
        "model_id": SYNTHETIC_MODEL_ID,
        "kind": "template-dtw",
        "vocabulary_version": "dev-local",
        "feature_spec_version": "fs-1",
        "developer_only": True,
    }
    assert len(client.get("/api/v1/vocabulary").json()["entries"]) == 3


def test_model_unavailable_is_503(client_factory: Callable[..., TestClient]) -> None:
    response = client_factory(model_mode="template").get("/api/v1/vocabulary")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"


def test_feature_spec(client: TestClient) -> None:
    spec = client.get("/api/v1/feature-spec").json()
    assert spec["version"] == "fs-1" and spec["shapes"]["face"] == [40, 3]


def test_diagnostics(client: TestClient) -> None:
    body = client.get("/api/v1/diagnostics").json()
    assert body["rss_mb"] > 0
    assert body["model"]["model_id"] == "mock"
    assert body["server_extraction"]["available"] is False
