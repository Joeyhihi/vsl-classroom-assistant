from fastapi import APIRouter

from vsl_backend.api.v1 import health, models, recognition_ws, recordings

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(models.router)
router.include_router(recognition_ws.router)
router.include_router(recordings.router)
