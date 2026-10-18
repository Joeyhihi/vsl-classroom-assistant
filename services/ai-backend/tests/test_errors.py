from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from tests.conftest import make_settings
from vsl_backend.errors import AppError
from vsl_backend.main import create_app
from vsl_backend.schemas.common import ErrorCode, ErrorResponse

SECRET = "transcript text that must never be echoed"


class _Body(BaseModel):
    count: int


@pytest.fixture
def app_with_test_routes() -> Iterator[FastAPI]:
    app = create_app(make_settings())

    @app.get("/_test/boom")
    async def boom() -> None:
        raise RuntimeError(SECRET)

    @app.get("/_test/app-error")
    async def app_error() -> None:
        raise AppError(ErrorCode.MODEL_UNAVAILABLE, "No usable sign model", 503)

    @app.post("/_test/validate")
    async def validate(body: _Body) -> _Body:
        return body

    yield app


def _client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_unknown_route_uses_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    ErrorResponse.model_validate(response.json())
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_unhandled_error_is_internal_and_does_not_leak(app_with_test_routes: FastAPI) -> None:
    response = _client(app_with_test_routes).get("/_test/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL"
    assert SECRET not in response.text


def test_app_error_maps_code_and_status(app_with_test_routes: FastAPI) -> None:
    response = _client(app_with_test_routes).get("/_test/app-error")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"


def test_validation_error_does_not_echo_input(app_with_test_routes: FastAPI) -> None:
    response = _client(app_with_test_routes).post("/_test/validate", json={"count": SECRET})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert SECRET not in response.text
