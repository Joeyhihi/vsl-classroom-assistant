from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from vsl_backend.config import Settings
from vsl_backend.main import create_app

ALLOWED_ORIGIN = "http://localhost:5173"


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
