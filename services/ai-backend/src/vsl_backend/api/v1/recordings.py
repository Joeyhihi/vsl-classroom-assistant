"""Recorder and review endpoints (Phase 4). Off unless VSL_RECORDER_ENABLED=true."""

from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from vsl_backend.recording.service import RecorderService
from vsl_backend.schemas.recognition import WireFrame
from vsl_backend.schemas.recordings import (
    RecorderConfig,
    ReviewCreate,
    SampleCreate,
    SampleFrames,
    SampleList,
    SampleSummary,
    SessionCreate,
    SessionCreated,
)
from vsl_features.dataset import load_frames
from vsl_features.frames import frame_to_wire

router = APIRouter(prefix="/recordings")


def _service(request: Request) -> RecorderService:
    service: RecorderService = request.app.state.recorder
    return service


@router.get("/config", response_model=RecorderConfig)
async def config(request: Request) -> RecorderConfig:
    return _service(request).config()


@router.post("/sessions", response_model=SessionCreated, status_code=201)
async def create_session(request: Request, body: SessionCreate) -> SessionCreated:
    session = _service(request).create_session(body)
    return SessionCreated(session_id=session.session_id, signer_id=session.signer_id)


@router.post("/sessions/{session_id}/samples", response_model=SampleSummary, status_code=201)
async def add_sample(request: Request, session_id: str, body: SampleCreate) -> SampleSummary:
    # File writes are blocking; keep the event loop (and live recognition) free.
    return await run_in_threadpool(_service(request).add_sample, session_id, body)


@router.get("/samples", response_model=SampleList)
async def list_samples(
    request: Request, session_id: str | None = None, status: str | None = None
) -> SampleList:
    return SampleList(samples=_service(request).list_samples(session_id, status))


@router.get("/samples/{sample_id}/frames", response_model=SampleFrames)
async def sample_frames(request: Request, sample_id: str) -> SampleFrames:
    service = _service(request)
    view = service.sample_view(sample_id)
    frames = await run_in_threadpool(load_frames, service.sample_path(view))
    return SampleFrames(
        sample_id=sample_id,
        image_width=view.record.image_w,
        image_height=view.record.image_h,
        frames=[WireFrame.model_validate(frame_to_wire(f)) for f in frames],
    )


@router.post("/samples/{sample_id}/review", response_model=SampleSummary)
async def review(request: Request, sample_id: str, body: ReviewCreate) -> SampleSummary:
    return await run_in_threadpool(_service(request).review, sample_id, body)
