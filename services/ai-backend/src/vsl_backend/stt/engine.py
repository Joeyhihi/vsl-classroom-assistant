"""faster-whisper speech-to-text engine (P7, ADR-015): CPU int8 by default.

A heavy engine for the ResourceManager: nothing is imported or loaded until the
first transcription. The model is downloaded by faster-whisper into
`model-artifacts/stt/` on first use (Windows only; the M1 never enables STT).

Post-G7 GPU opt-in: with `VSL_STT_DEVICE=cuda`, a CUDA out-of-memory error at
load or transcription falls back to CPU int8 once, and stays there.
"""

from __future__ import annotations

import gc
import importlib.util
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

CPU_FALLBACK = ("cpu", "int8")


class Transcriber(Protocol):
    def transcribe(
        self, audio: NDArray[np.float32], **kwargs: Any
    ) -> tuple[Iterable[Any], Any]: ...


# (model, device, compute_type, download_root) → transcriber
TranscriberFactory = Callable[[str, str, str, Path], Transcriber]


@dataclass(frozen=True)
class Segment:
    start_ms: int
    end_ms: int
    text: str


class SttUnavailable(Exception):
    """faster-whisper is not installed or the model could not be loaded."""


def faster_whisper_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def _faster_whisper(model: str, device: str, compute_type: str, root: Path) -> Transcriber:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SttUnavailable("faster-whisper is not installed (uv run --extra stt ...)") from None
    transcriber: Transcriber = WhisperModel(
        model, device=device, compute_type=compute_type, download_root=str(root), cpu_threads=4
    )
    return transcriber


def _is_cuda_oom(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "out of memory" in text and ("cuda" in text or "cublas" in text or "device" in text)


class SttEngine:
    name = "stt"
    heavy = True

    def __init__(
        self,
        model: str,
        device: str,
        compute_type: str,
        download_root: Path,
        factory: TranscriberFactory = _faster_whisper,
    ) -> None:
        self.model = model
        self.device = device
        self.compute_type = compute_type
        self.download_root = download_root
        self._factory = factory
        self._transcriber: Transcriber | None = None
        self.fell_back_to_cpu = False

    @property
    def detail(self) -> str:
        mode = "cpu (fallback)" if self.fell_back_to_cpu else self.device
        return f"model={self.model} device={mode} compute={self.compute_type}"

    def load(self) -> None:
        try:
            self._transcriber = self._create()
        except SttUnavailable:
            raise
        except Exception as exc:  # CTranslate2 raises RuntimeError on CUDA problems
            if self.device != "cpu" and _is_cuda_oom(exc):
                self._fall_back()
                self._transcriber = self._create()
            else:
                logger.warning("STT model failed to load: %s", type(exc).__name__)
                raise SttUnavailable("speech model could not be loaded") from None

    def unload(self) -> None:
        self._transcriber = None
        gc.collect()

    def transcribe(self, audio: NDArray[np.float32], language: str) -> list[Segment]:
        if self._transcriber is None:
            raise SttUnavailable("speech model is not loaded")
        try:
            return self._run(audio, language)
        except Exception as exc:
            if self.device != "cpu" and not self.fell_back_to_cpu and _is_cuda_oom(exc):
                self._fall_back()
                self._transcriber = self._create()
                return self._run(audio, language)
            raise

    def _create(self) -> Transcriber:
        self.download_root.mkdir(parents=True, exist_ok=True)
        return self._factory(self.model, self.device, self.compute_type, self.download_root)

    def _fall_back(self) -> None:
        logger.warning("CUDA out of memory: STT falls back to CPU int8")
        self.unload()
        self.device, self.compute_type = CPU_FALLBACK
        self.fell_back_to_cpu = True

    def _run(self, audio: NDArray[np.float32], language: str) -> list[Segment]:
        assert self._transcriber is not None
        segments, _info = self._transcriber.transcribe(
            audio, language=language, beam_size=1, vad_filter=True, condition_on_previous_text=False
        )
        out = []
        for s in segments:  # a generator: decoding happens while iterating
            text = str(s.text).strip()
            if text:
                out.append(Segment(round(float(s.start) * 1000), round(float(s.end) * 1000), text))
        return out
