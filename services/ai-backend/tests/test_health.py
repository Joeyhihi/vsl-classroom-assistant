from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from vsl_backend.schemas.health import HealthResponse

EXAMPLES = Path(__file__).parent / "contract_examples"


def test_health_mock_mode_is_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = HealthResponse.model_validate(response.json())
    assert body.status == "ok"
    assert body.model_mode == "mock"
    assert body.components.sign_model.status == "mock"
    assert body.components.stt.status == "disabled"
    assert body.components.tts.status == "disabled"


def test_health_matches_shared_contract_example(client: TestClient) -> None:
    # The same file is validated by the frontend type guard (apps/web).
    example = json.loads((EXAMPLES / "health.mock.json").read_text(encoding="utf-8"))
    HealthResponse.model_validate(example)
    assert client.get("/api/v1/health").json() == example


def test_health_degraded_when_model_mode_not_implemented(
    client_factory: Callable[..., TestClient],
) -> None:
    body = client_factory(model_mode="template").get("/api/v1/health").json()

    assert body["status"] == "degraded"
    assert body["components"]["sign_model"]["status"] == "unavailable"


def test_health_reports_stt_unavailable_when_enabled_in_phase_1(
    client_factory: Callable[..., TestClient],
) -> None:
    body = client_factory(stt_enabled=True).get("/api/v1/health").json()

    assert body["status"] == "degraded"
    assert body["components"]["stt"]["status"] == "unavailable"
