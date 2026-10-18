"""POST /api/v1/feedback and DELETE /api/v1/feedback (Phase 6)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool

from vsl_backend.errors import AppError
from vsl_backend.feedback_store import DatasetError, FeedbackStore
from vsl_backend.schemas.common import ErrorCode
from vsl_backend.schemas.feedback import FeedbackCreate, FeedbackCreated

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feedback")


def _store(request: Request) -> FeedbackStore:
    store: FeedbackStore = request.app.state.feedback
    return store


@router.post("", response_model=FeedbackCreated, status_code=201)
async def create_feedback(request: Request, body: FeedbackCreate) -> FeedbackCreated:
    try:
        feedback_id = await run_in_threadpool(_store(request).append, body.model_dump())
    except DatasetError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, str(exc), 422) from None
    logger.info("feedback recorded")  # never the content (privacy)
    return FeedbackCreated(feedback_id=feedback_id)


@router.delete("", status_code=204)
async def delete_feedback(request: Request) -> Response:
    await run_in_threadpool(_store(request).delete_all)
    return Response(status_code=204)
