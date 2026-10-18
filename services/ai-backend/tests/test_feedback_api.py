from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import ALLOWED_ORIGIN, REPO_ROOT

HEADERS = {"Origin": ALLOWED_ORIGIN}
BODY: dict[str, Any] = {
    "session_id": "sess-1",
    "prediction_id": "pred-1",
    "model_id": "vsl-01",
    "predicted_gloss_id": "DEV_01",
    "confidence": 0.82,
    "verdict": "incorrect",
    "expected_gloss_id": "DEV_02",
}


@pytest.fixture
def client(client_factory: Callable[..., TestClient], tmp_path: Path) -> TestClient:
    return client_factory(data_root=tmp_path)


def rows(root: Path) -> list[dict[str, Any]]:
    path = root / "feedback" / "feedback.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_feedback_is_appended_to_data_root(client: TestClient, tmp_path: Path) -> None:
    first = client.post("/api/v1/feedback", json=BODY, headers=HEADERS)
    second = client.post(
        "/api/v1/feedback",
        json={**BODY, "verdict": "correct", "expected_gloss_id": None},
        headers=HEADERS,
    )

    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["feedback_id"] != second.json()["feedback_id"]
    saved = rows(tmp_path)
    assert [r["verdict"] for r in saved] == ["incorrect", "correct"]
    assert saved[0]["expected_gloss_id"] == "DEV_02" and "at" in saved[0]


def test_delete_removes_everything(client: TestClient, tmp_path: Path) -> None:
    client.post("/api/v1/feedback", json=BODY, headers=HEADERS)
    assert client.delete("/api/v1/feedback", headers=HEADERS).status_code == 204
    assert not (tmp_path / "feedback" / "feedback.jsonl").exists()
    assert client.delete("/api/v1/feedback", headers=HEADERS).status_code == 204  # idempotent


@pytest.mark.parametrize(
    "change",
    [
        {"comment": "free text is not allowed"},
        {"verdict": "maybe"},
        {"confidence": 1.5},
        {"expected_gloss_id": "not a gloss"},
        {"session_id": "../../etc"},
    ],
)
def test_invalid_feedback_is_rejected(client: TestClient, change: dict[str, Any]) -> None:
    response = client.post("/api/v1/feedback", json={**BODY, **change}, headers=HEADERS)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_data_root_inside_the_repo_is_refused(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(data_root=REPO_ROOT / "data")
    response = client.post("/api/v1/feedback", json=BODY, headers=HEADERS)
    assert response.status_code == 422
    assert "outside the repository" in response.json()["error"]["message"]
    assert not (REPO_ROOT / "data").exists()


def test_feedback_needs_an_allowed_origin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/feedback", json=BODY, headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403
