"""POST /api/v1/stt/transcriptions (P7, gated by VSL_STT_ENABLED). Audio is never stored."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, File, Form, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from vsl_backend.errors import AppError
from vsl_backend.schemas.common import ErrorCode
from vsl_backend.schemas.stt import TranscriptionResponse, TranscriptSegment
from vsl_backend.stt.audio import SAMPLE_RATE, AudioError, parse_wav
from vsl_backend.stt.engine import SttUnavailable
from vsl_backend.stt.service import SttService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stt")


@router.post("/transcriptions", response_model=TranscriptionResponse)
async def transcribe(
    request: Request,
    audio: UploadFile = File(...),  # noqa: B008 (FastAPI dependency marker)
    language: str = Form("vi"),
) -> TranscriptionResponse:
    service: SttService = request.app.state.stt
    if service.engine is None:
        raise AppError(
            ErrorCode.STT_UNAVAILABLE, service.unavailable or "speech-to-text is disabled", 503
        )
    if language != "vi":
        raise AppError(ErrorCode.VALIDATION_ERROR, "only language=vi is supported", 422)
    data = await audio.read()
    try:
        samples = parse_wav(data, service.max_audio_s)
    except AudioError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, str(exc), 422) from None

    started = time.perf_counter()
    try:
        segments = await run_in_threadpool(service.transcribe, samples)
    except SttUnavailable as exc:
        raise AppError(ErrorCode.STT_UNAVAILABLE, str(exc), 503) from None
    processing_ms = round((time.perf_counter() - started) * 1000)
    # Timing only: transcript text and audio are never logged (privacy).
    logger.info("transcribed %.1f s of audio in %d ms", len(samples) / SAMPLE_RATE, processing_ms)
    return TranscriptionResponse(
        text=" ".join(s.text for s in segments),
        segments=[
            TranscriptSegment(start_ms=s.start_ms, end_ms=s.end_ms, text=s.text) for s in segments
        ],
        duration_ms=round(len(samples) / SAMPLE_RATE * 1000),
        model_id=service.engine.model,
        processing_ms=processing_ms,
    )
