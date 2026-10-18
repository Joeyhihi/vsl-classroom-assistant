"""STT service: gating, health status and one transcription at a time (docs/API_CONTRACTS.md)."""

from __future__ import annotations

import threading

import numpy as np
from numpy.typing import NDArray

from vsl_backend.config import Settings
from vsl_backend.inference.resource_manager import ResourceManager
from vsl_backend.schemas.health import ComponentHealth
from vsl_backend.stt.engine import Segment, SttEngine, SttUnavailable, faster_whisper_available


class SttService:
    def __init__(
        self,
        settings: Settings,
        resources: ResourceManager,
        engine: SttEngine | None = None,
        installed: bool | None = None,
    ) -> None:
        self.enabled = settings.stt_enabled
        self.max_audio_s = settings.stt_max_audio_s
        self.language = "vi"
        self._resources = resources
        self._lock = threading.Lock()  # CPU STT: one job at a time
        self.unavailable: str | None = None
        self.engine: SttEngine | None = None
        if not self.enabled:
            return
        if not (faster_whisper_available() if installed is None else installed):
            self.unavailable = "faster-whisper is not installed (uv run --extra stt ...)"
            return
        self.engine = engine or SttEngine(
            settings.stt_model,
            settings.stt_device,
            settings.stt_compute_type,
            settings.model_artifacts_dir / "stt",
        )
        resources.register(self.engine)

    def health(self) -> ComponentHealth:
        if not self.enabled:
            return ComponentHealth(status="disabled")
        if self.engine is None or self.unavailable:
            return ComponentHealth(status="unavailable", detail=self.unavailable)
        resident = any(s.resident for s in self._resources.status() if s.name == self.engine.name)
        return ComponentHealth(
            status="ready", detail=f"{self.engine.detail} resident={str(resident).lower()}"
        )

    def transcribe(self, audio: NDArray[np.float32]) -> list[Segment]:
        """Blocking: call from a threadpool. Raises SttUnavailable or ResourceExhausted."""
        if self.engine is None:
            raise SttUnavailable(self.unavailable or "speech-to-text is disabled")
        with self._lock:
            engine = self._resources.acquire(self.engine.name)
            assert isinstance(engine, SttEngine)
            return engine.transcribe(audio, self.language)
