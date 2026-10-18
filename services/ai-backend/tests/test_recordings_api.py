from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import REPO_ROOT, load_replay

VOCAB = REPO_ROOT / "ml" / "vocabulary" / "vocabulary.dev.json"
SESSION_BODY: dict[str, Any] = {
    "signer_id": "DEV-01",
    "consent_id": "SELF",
    "dominant_hand": "right",
    "conditions": {"lighting": "normal", "background": "plain", "distance": "normal"},
    "image_width": 640,
    "image_height": 480,
    "feature_spec_version": "fs-1",
    "extractor_version": "tasks-vision@1.0.1",
    "extractor_backend": "browser-L2",
}


@pytest.fixture
def recorder(client_factory: Callable[..., TestClient], tmp_path: Path) -> TestClient:
    return client_factory(
        recorder_enabled=True, data_root=tmp_path / "data", dev_vocabulary_path=VOCAB
    )


def take(n: int = 45, start: int = 0) -> list[dict[str, Any]]:
    """A ~3 s take from the synthetic replay (no real person)."""
    frames: list[dict[str, Any]] = load_replay()["frames"][start : start + n]
    return frames


def start_session(client: TestClient, **overrides: Any) -> str:
    response = client.post("/api/v1/recordings/sessions", json=SESSION_BODY | overrides)
    assert response.status_code == 201, response.text
    session_id: str = response.json()["session_id"]
    return session_id


def post_sample(client: TestClient, session_id: str, label: str = "DEV_01", **kw: Any) -> Any:
    body = {"label": label, "take_ms": 3000, "frames": take(**kw)}
    return client.post(f"/api/v1/recordings/sessions/{session_id}/samples", json=body)


def test_disabled_by_default(client: TestClient) -> None:
    config = client.get("/api/v1/recordings/config").json()
    assert config["enabled"] is False and "VSL_RECORDER_ENABLED" in config["reason"]
    response = client.post("/api/v1/recordings/sessions", json=SESSION_BODY)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "RECORDER_DISABLED"


def test_config_lists_the_dev_vocabulary(recorder: TestClient, tmp_path: Path) -> None:
    config = recorder.get("/api/v1/recordings/config").json()
    assert config["enabled"] and config["developer_only_vocabulary"]
    assert config["third_party_allowed"] is False
    assert config["data_root"] == str(tmp_path / "data")
    assert {i["sample_kind"] for i in config["items"]} == {"target", "distractor", "background"}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"consent_id": "C-1234", "signer_id": "SGN-0001"}, "blocked until the consent package"),
        ({"signer_id": "SGN-0001"}, "only for the developer"),
        ({"signer_id": "Nguyen Van A"}, "pseudonymous"),
    ],
)
def test_consent_rule_is_enforced(
    recorder: TestClient, overrides: dict[str, str], message: str
) -> None:
    response = recorder.post("/api/v1/recordings/sessions", json=SESSION_BODY | overrides)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CONSENT_REQUIRED"
    assert message in response.json()["error"]["message"]


def test_third_party_needs_the_explicit_setting(
    client_factory: Callable[..., TestClient], tmp_path: Path
) -> None:
    client = client_factory(
        recorder_enabled=True,
        third_party_recording_enabled=True,
        data_root=tmp_path,
        dev_vocabulary_path=VOCAB,
    )
    start_session(client, consent_id="C-1234", signer_id="SGN-0001")


def test_session_validation(recorder: TestClient) -> None:
    bad = recorder.post(
        "/api/v1/recordings/sessions", json=SESSION_BODY | {"conditions": {"mood": "x"}}
    )
    assert bad.status_code == 422
    spec = recorder.post(
        "/api/v1/recordings/sessions", json=SESSION_BODY | {"feature_spec_version": "fs-0"}
    )
    assert spec.json()["error"]["code"] == "FEATURE_SPEC_MISMATCH"


def test_sample_is_written_outside_the_repo_with_a_manifest_row(
    recorder: TestClient, tmp_path: Path
) -> None:
    session_id = start_session(recorder)
    response = post_sample(recorder, session_id)

    assert response.status_code == 201, response.text
    sample = response.json()
    assert sample["status"] == "pending" and sample["sample_kind"] == "target"
    assert sample["n_frames"] == 45 and sample["dropped_frames"] == 0
    npz = list((tmp_path / "data" / "landmarks" / "DEV-01" / session_id).glob("*.npz"))
    assert len(npz) == 1
    rows = (tmp_path / "data" / "manifests" / "samples.jsonl").read_text(encoding="utf-8")
    assert json.loads(rows)["consent_id"] == "SELF"


def test_large_takes_fit_the_recording_body_limit(recorder: TestClient) -> None:
    session_id = start_session(recorder)
    body = {"label": "DEV_01", "take_ms": 6000, "frames": take(n=90)}  # ~6 s, well above 64 KB
    assert len(json.dumps(body)) > 64 * 1024
    response = recorder.post(f"/api/v1/recordings/sessions/{session_id}/samples", json=body)
    assert response.status_code == 201, response.text


def test_invalid_frames_are_dropped_and_mostly_invalid_takes_refused(recorder: TestClient) -> None:
    session_id = start_session(recorder)
    frames = take(n=10)
    frames[2] = dict(frames[2], right_hand=[[9.0, 9.0, 0.0]] * 21)
    frames[5] = dict(frames[5], t_ms=0)  # out of order
    ok = recorder.post(
        f"/api/v1/recordings/sessions/{session_id}/samples",
        json={"label": "DEV_01", "take_ms": 3000, "frames": frames},
    )
    assert ok.status_code == 201 and ok.json()["dropped_frames"] == 2

    garbage = [dict(f, pose=[[5.0, 5.0, 0.0, 1.0]] * 33) for f in take(n=10)]
    refused = recorder.post(
        f"/api/v1/recordings/sessions/{session_id}/samples",
        json={"label": "DEV_01", "take_ms": 3000, "frames": garbage},
    )
    assert refused.status_code == 422 and "too many invalid frames" in refused.text


def test_labels_and_sessions_are_checked(recorder: TestClient) -> None:
    session_id = start_session(recorder)
    assert post_sample(recorder, session_id, label="NOT_IN_VOCAB").status_code == 422
    assert post_sample(recorder, "S20991231-000000-ffff").status_code == 404


def test_background_kind_comes_from_the_vocabulary(recorder: TestClient) -> None:
    session_id = start_session(recorder)
    assert (
        post_sample(recorder, session_id, label="REST_DESK").json()["sample_kind"] == "background"
    )


def test_list_frames_and_review(recorder: TestClient) -> None:
    session_id = start_session(recorder)
    a = post_sample(recorder, session_id).json()["sample_id"]
    b = post_sample(recorder, session_id, start=50).json()["sample_id"]

    listed = recorder.get("/api/v1/recordings/samples", params={"status": "pending"}).json()
    assert [s["sample_id"] for s in listed["samples"]] == [a, b]

    frames = recorder.get(f"/api/v1/recordings/samples/{a}/frames").json()
    assert len(frames["frames"]) == 45 and frames["image_width"] == 640

    accepted = recorder.post(
        f"/api/v1/recordings/samples/{a}/review", json={"status": "accepted", "reviewer": "DEV-01"}
    )
    assert accepted.json()["status"] == "accepted"
    relabel = recorder.post(
        f"/api/v1/recordings/samples/{b}/review",
        json={"status": "relabelled", "reviewer": "DEV-01", "relabel_to": "DEV_02"},
    ).json()
    assert relabel["label"] == "DEV_02" and relabel["recorded_label"] == "DEV_01"

    no_reason = recorder.post(
        f"/api/v1/recordings/samples/{a}/review", json={"status": "rejected", "reviewer": "DEV-01"}
    )
    assert no_reason.status_code == 422
    bad_relabel = recorder.post(
        f"/api/v1/recordings/samples/{a}/review",
        json={"status": "relabelled", "reviewer": "DEV-01", "relabel_to": "NOPE"},
    )
    assert bad_relabel.status_code == 422
    assert recorder.get("/api/v1/recordings/samples/unknown/frames").status_code == 404


def test_data_root_inside_the_repository_disables_the_recorder(
    client_factory: Callable[..., TestClient],
) -> None:
    client = client_factory(
        recorder_enabled=True, data_root=REPO_ROOT / "data", dev_vocabulary_path=VOCAB
    )
    config = client.get("/api/v1/recordings/config").json()
    assert config["enabled"] is False and "outside the repository" in config["reason"]
    assert not (REPO_ROOT / "data").exists()
