"""P9: the backend serves a (fake) built SPA on one origin."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from vsl_backend.static import PAGE_CONTENT_SECURITY_POLICY, web_unavailable_reason


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (root / "assets" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside dist", encoding="utf-8")
    return root


@pytest.fixture
def web(client_factory: Callable[..., TestClient], dist: Path) -> TestClient:
    return client_factory(serve_web=True, web_dist_dir=dist)


def test_index_and_spa_fallback_with_page_csp(web: TestClient) -> None:
    for path in ("/", "/settings", "/some/view"):
        response = web.get(path)
        assert response.status_code == 200 and "id=root" in response.text
        assert response.headers["content-security-policy"] == PAGE_CONTENT_SECURITY_POLICY
        assert response.headers["cache-control"] == "no-cache"
    assert "'wasm-unsafe-eval'" in PAGE_CONTENT_SECURITY_POLICY  # MediaPipe needs WebAssembly


def test_hashed_assets_are_cached(web: TestClient) -> None:
    response = web.get("/assets/index-abc.js")
    assert response.status_code == 200 and "immutable" in response.headers["cache-control"]


def test_missing_files_and_api_paths_are_404(web: TestClient) -> None:
    assert web.get("/mediapipe/missing.task").status_code == 404
    response = web.get("/api/v1/does-not-exist")
    assert response.status_code == 404 and response.json()["error"]["code"] == "NOT_FOUND"
    assert web.get("/api/v1/health").json()["status"] in ("ok", "degraded")  # API untouched


def test_no_path_traversal(web: TestClient) -> None:
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        assert "outside dist" not in web.get(path).text


def test_same_origin_is_allowed_when_serving(web: TestClient) -> None:
    response = web.post("/api/v1/feedback", json={}, headers={"Origin": "http://127.0.0.1:8000"})
    assert response.status_code == 422  # reached validation, not ORIGIN_FORBIDDEN


def test_not_served_by_default(client_factory: Callable[..., TestClient], dist: Path) -> None:
    client = client_factory(web_dist_dir=dist)
    assert client.get("/").status_code == 404
    assert web_unavailable_reason(make_settings(serve_web=True, web_dist_dir=dist / "x"))
    assert "http://127.0.0.1:8000" not in make_settings().allowed_origin_list
