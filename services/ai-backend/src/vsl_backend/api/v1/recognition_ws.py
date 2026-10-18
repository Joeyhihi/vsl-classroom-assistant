"""WS /api/v1/recognition/ws — transport for `RecognitionSession`."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocketDisconnect, WebSocketState

from vsl_backend.config import Settings
from vsl_backend.extraction.server_extractor import (
    ServerLandmarkExtractor,
    extraction_unavailable_reason,
)
from vsl_backend.recognition.session import CloseCode, Outcome, RecognitionSession

router = APIRouter()
logger = logging.getLogger(__name__)


def _session_for(websocket: WebSocket) -> RecognitionSession:
    settings: Settings = websocket.app.state.settings
    unavailable = extraction_unavailable_reason(
        settings.server_extraction_enabled, settings.holistic_model_path
    )
    return RecognitionSession(
        settings,
        websocket.app.state.classifier,
        extractor_factory=lambda: ServerLandmarkExtractor(settings.holistic_model_path),
        extraction_unavailable=unavailable,
    )


async def _send(websocket: WebSocket, outcome: Outcome) -> bool:
    """Send messages; returns False once the connection has been closed."""
    for message in outcome.messages:
        await websocket.send_text(message.model_dump_json())
    if outcome.close_code is not None:
        await websocket.close(code=outcome.close_code)
        return False
    return True


@router.websocket("/recognition/ws")
async def recognition_ws(websocket: WebSocket) -> None:
    settings: Settings = websocket.app.state.settings
    origin = websocket.headers.get("origin")
    # Browsers always send Origin on WebSockets; rejecting unknown origins
    # prevents other sites in the same browser from using the local backend.
    if origin is not None and origin not in settings.allowed_origin_list:
        await websocket.close(code=CloseCode.POLICY)
        return

    await websocket.accept()
    session = _session_for(websocket)
    try:
        while True:
            timeout = session.check_timeouts()
            if timeout is not None:
                await _send(websocket, timeout)
                return
            try:
                message = await asyncio.wait_for(
                    websocket.receive(), timeout=settings.heartbeat_timeout_s
                )
            except TimeoutError:
                await websocket.close(code=CloseCode.HEARTBEAT_TIMEOUT)
                return
            if message["type"] == "websocket.disconnect":
                return
            if message.get("text") is not None:
                outcome = session.handle_text(message["text"])
            elif message.get("bytes") is not None:
                # JPEG decode + MediaPipe are CPU-bound; keep the event loop free.
                outcome = await run_in_threadpool(session.handle_binary, message["bytes"])
            else:
                continue
            if not await _send(websocket, outcome):
                return
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("recognition session failed session_id=%s", session.session_id)
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=CloseCode.INTERNAL)
