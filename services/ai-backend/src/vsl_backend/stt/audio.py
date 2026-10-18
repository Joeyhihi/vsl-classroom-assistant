"""WAV validation for push-to-talk audio (docs/API_CONTRACTS.md, STT): 16 kHz mono 16-bit PCM."""

from __future__ import annotations

import io
import wave

import numpy as np
from numpy.typing import NDArray

SAMPLE_RATE = 16_000


class AudioError(ValueError):
    """Safe to show: describes the format, never the content."""


def parse_wav(data: bytes, max_seconds: float) -> NDArray[np.float32]:
    """16-bit PCM mono 16 kHz WAV → float32 samples in [-1, 1]."""
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
            n_frames = wav.getnframes()
            if channels != 1 or width != 2 or rate != SAMPLE_RATE:
                raise AudioError(
                    f"audio must be 16-bit mono {SAMPLE_RATE} Hz WAV "
                    f"(got {channels} ch, {8 * width}-bit, {rate} Hz)"
                )
            if n_frames == 0:
                raise AudioError("audio is empty")
            if n_frames / rate > max_seconds:
                raise AudioError(f"audio is longer than {max_seconds:g} s")
            pcm = wav.readframes(n_frames)
    except (wave.Error, EOFError):
        raise AudioError("audio is not a valid WAV file") from None
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    return samples
