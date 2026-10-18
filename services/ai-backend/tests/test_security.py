from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.conftest import ALLOWED_ORIGIN


def test_disallowed_origin_is_rejected_with_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "ORIGIN_FORBIDDEN"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_allowed_origin_and_no_origin_pass(client: TestClient) -> None:
    assert client.get("/api/v1/health", headers={"Origin": ALLOWED_ORIGIN}).status_code == 200
    assert client.get("/api/v1/health").status_code == 200


def test_security_headers_present(client: TestClient) -> None:
    headers = client.get("/api/v1/health").headers

    assert "connect-src 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert len(headers["X-Request-ID"]) == 32


def test_oversized_body_rejected(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(max_body_bytes=10)

    response = client.post("/api/v1/health", content=b"x" * 11)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_docs_disabled_in_prod(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(env="prod", model_mode="onnx")

    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404
