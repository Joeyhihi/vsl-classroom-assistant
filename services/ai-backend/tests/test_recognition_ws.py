from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import ALLOWED_ORIGIN, SYNTHETIC_MODEL_ID, load_replay
from tests.test_session import start_message

WS = "/api/v1/recognition/ws"


def run_replay(client: TestClient) -> list[dict[str, Any]]:
    replay = load_replay()
    received: list[dict[str, Any]] = []
    with client.websocket_connect(WS, headers={"Origin": ALLOWED_ORIGIN}) as ws:
        ws.send_text(start_message())
        received.append(json.loads(ws.receive_text()))
        frames = replay["frames"]
        for i in range(0, len(frames), 2):
            ws.send_text(json.dumps({"type": "frames.batch", "frames": frames[i : i + 2]}))
            ws.send_text('{"type": "ping"}')
            while True:  # read until the pong for this batch
                msg = json.loads(ws.receive_text())
                if msg["type"] == "pong":
                    break
                received.append(msg)
        ws.send_text('{"type": "session.stop"}')
        received.append(json.loads(ws.receive_text()))
    return received


def test_foreign_origin_is_refused(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as info,
        client.websocket_connect(WS, headers={"Origin": "https://evil.example"}),
    ):
        pass
    assert info.value.code == 1008


def test_mock_mode_end_to_end(client_factory: Callable[..., TestClient]) -> None:
    received = run_replay(client_factory(max_fps=200))

    assert received[0]["type"] == "session.started"
    assert received[-1] == {"type": "session.stopped", "reason": "client_stop"}
    predictions = [m for m in received if m["type"] == "prediction"]
    assert [p["status"] for p in predictions] == ["confident", "uncertain", "rejected"]
    assert {m["state"] for m in received if m["type"] == "status"} <= {
        "waiting_for_hands",
        "ready",
        "signing",
    }


def test_template_mode_recognises_the_synthetic_signs(
    client_factory: Callable[..., TestClient], artifacts_dir: Path
) -> None:
    client = client_factory(
        model_mode="template",
        sign_model_id=SYNTHETIC_MODEL_ID,
        model_artifacts_dir=artifacts_dir,
        max_fps=200,
    )
    predictions = [m for m in run_replay(client) if m["type"] == "prediction"]

    assert [p["top"][0]["gloss_id"] for p in predictions] == ["SYN_A", "SYN_B", "SYN_C"]
    assert all(
        p["status"] == "confident" and p["model_id"] == SYNTHETIC_MODEL_ID for p in predictions
    )


def test_protocol_error_closes_with_code(client: TestClient) -> None:
    with client.websocket_connect(WS) as ws:
        ws.send_text(start_message(protocol_version=99))
        assert json.loads(ws.receive_text())["code"] == "PROTOCOL_MISMATCH"
        with pytest.raises(WebSocketDisconnect) as info:
            ws.receive_text()
    assert info.value.code == 4001


def test_heartbeat_timeout(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory(heartbeat_timeout_s=0.2)
    with client.websocket_connect(WS) as ws, pytest.raises(WebSocketDisconnect) as info:
        ws.receive_text()
    assert info.value.code == 4004


def test_uvicorn_has_a_websocket_implementation() -> None:
    """TestClient works without one, but the real server returns 404 on upgrade."""
    import importlib.util

    assert importlib.util.find_spec("websockets") or importlib.util.find_spec("wsproto")
