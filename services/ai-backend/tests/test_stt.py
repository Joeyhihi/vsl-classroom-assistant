"""STT with a fake transcriber: no faster-whisper and no model on the M1."""

from __future__ import annotations

import io
import wave
from collections.abc import Callable, Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from numpy.typing import NDArray

from tests.conftest import ALLOWED_ORIGIN, make_settings
from vsl_backend.inference.resource_manager import ResourceManager
from vsl_backend.stt.audio import AudioError, parse_wav
from vsl_backend.stt.engine import SttEngine, SttUnavailable
from vsl_backend.stt.service import SttService

HEADERS = {"Origin": ALLOWED_ORIGIN}


def wav_bytes(seconds: float = 1.0, rate: int = 16_000, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        tone = (np.sin(np.arange(int(seconds * rate)) / 8) * 8000).astype("<i2")
        wav.writeframes(np.repeat(tone, channels).tobytes())
    return buffer.getvalue()


class FakeTranscriber:
    def __init__(self, fail_with: Exception | None = None) -> None:
        self.fail_with = fail_with
        self.calls: list[dict[str, Any]] = []

    def transcribe(self, audio: NDArray[np.float32], **kwargs: Any) -> tuple[Iterable[Any], Any]:
        self.calls.append(kwargs)
        if self.fail_with:
            raise self.fail_with
        segments = [
            SimpleNamespace(start=0.0, end=0.8, text=" Xin chào "),
            SimpleNamespace(start=0.8, end=1.0, text="  "),
            SimpleNamespace(start=1.0, end=1.6, text="các em"),
        ]
        return iter(segments), None


class Factory:
    def __init__(self, *transcribers: FakeTranscriber, fail_first: Exception | None = None) -> None:
        self.transcribers = list(transcribers)
        self.fail_first = fail_first
        self.created: list[tuple[str, str]] = []

    def __call__(self, model: str, device: str, compute: str, root: Path) -> FakeTranscriber:
        self.created.append((device, compute))
        if self.fail_first is not None:
            error, self.fail_first = self.fail_first, None
            raise error
        return self.transcribers.pop(0)


def engine(tmp_path: Path, factory: Factory, device: str = "cpu") -> SttEngine:
    return SttEngine("small", device, "int8", tmp_path / "stt", factory)


# --- audio -------------------------------------------------------------------------


def test_parse_wav_returns_normalised_samples() -> None:
    samples = parse_wav(wav_bytes(0.5), max_seconds=30)
    assert samples.dtype == np.float32 and len(samples) == 8000
    assert np.abs(samples).max() <= 1.0


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (wav_bytes(rate=44_100), "16-bit mono 16000 Hz"),
        (wav_bytes(channels=2), "16-bit mono 16000 Hz"),
        (wav_bytes(seconds=31), "longer than 30 s"),
        (b"not audio", "not a valid WAV"),
        (wav_bytes(seconds=0), "empty"),
    ],
    # Short ids: pytest puts the test id in an environment variable, and Windows
    # limits those to 32767 characters (a WAV-bytes id breaks the Windows CI).
    ids=["44khz", "stereo", "too-long", "not-wav", "empty"],
)
def test_bad_audio_is_refused(data: bytes, message: str) -> None:
    with pytest.raises(AudioError, match=message):
        parse_wav(data, max_seconds=30)


# --- engine ------------------------------------------------------------------------


def test_engine_joins_non_empty_segments(tmp_path: Path) -> None:
    fake = FakeTranscriber()
    e = engine(tmp_path, Factory(fake))
    e.load()
    segments = e.transcribe(np.zeros(16_000, dtype=np.float32), "vi")

    assert [s.text for s in segments] == ["Xin chào", "các em"]
    assert segments[1].start_ms == 1000 and segments[1].end_ms == 1600
    assert fake.calls[0]["language"] == "vi"


def test_transcribe_before_load_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(SttUnavailable):
        engine(tmp_path, Factory()).transcribe(np.zeros(10, dtype=np.float32), "vi")


def test_cuda_oom_at_load_falls_back_to_cpu(tmp_path: Path) -> None:
    factory = Factory(FakeTranscriber(), fail_first=RuntimeError("CUDA failed: out of memory"))
    e = engine(tmp_path, factory, device="cuda")
    e.load()

    assert factory.created == [("cuda", "int8"), ("cpu", "int8")]
    assert e.fell_back_to_cpu and "cpu (fallback)" in e.detail


def test_cuda_oom_during_transcription_retries_on_cpu(tmp_path: Path) -> None:
    oom = FakeTranscriber(fail_with=RuntimeError("CUDA error: out of memory"))
    factory = Factory(oom, FakeTranscriber())
    e = engine(tmp_path, factory, device="cuda")
    e.load()

    segments = e.transcribe(np.zeros(10, dtype=np.float32), "vi")
    assert segments[0].text == "Xin chào"
    assert factory.created[-1] == ("cpu", "int8")


def test_other_load_errors_make_stt_unavailable(tmp_path: Path) -> None:
    factory = Factory(fail_first=OSError("model files missing"))
    with pytest.raises(SttUnavailable, match="could not be loaded"):
        engine(tmp_path, factory).load()


# --- service + API -----------------------------------------------------------------


def service(tmp_path: Path, **settings: Any) -> SttService:
    s = make_settings(stt_enabled=True, model_artifacts_dir=tmp_path, **settings)
    resources = ResourceManager(300, 0, free_ram=lambda: 8000.0)
    return SttService(s, resources, engine(tmp_path, Factory(FakeTranscriber())), installed=True)


def test_service_health_and_lazy_load(tmp_path: Path) -> None:
    svc = service(tmp_path)
    assert svc.health().status == "ready" and "resident=false" in (svc.health().detail or "")
    svc.transcribe(np.zeros(16_000, dtype=np.float32))
    assert "resident=true" in (svc.health().detail or "")


def test_service_without_faster_whisper_is_unavailable(tmp_path: Path) -> None:
    s = make_settings(stt_enabled=True, model_artifacts_dir=tmp_path)
    svc = SttService(s, ResourceManager(300, 0), installed=False)
    assert svc.health().status == "unavailable"
    assert svc.engine is None


@pytest.fixture
def stt_client(client_factory: Callable[..., TestClient], tmp_path: Path) -> TestClient:
    client = client_factory()
    client.app.state.stt = service(tmp_path)  # type: ignore[attr-defined]
    return client


def post(client: TestClient, data: bytes, language: str = "vi") -> Any:
    return client.post(
        "/api/v1/stt/transcriptions",
        files={"audio": ("clip.wav", data, "audio/wav")},
        data={"language": language},
        headers=HEADERS,
    )


def test_transcription_endpoint(stt_client: TestClient) -> None:
    response = post(stt_client, wav_bytes(1.5))
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Xin chào các em"
    assert body["duration_ms"] == 1500 and body["model_id"] == "small"
    assert len(body["segments"]) == 2 and body["processing_ms"] >= 0


def test_endpoint_rejects_bad_audio_and_language(stt_client: TestClient) -> None:
    assert post(stt_client, wav_bytes(rate=8000)).json()["error"]["code"] == "VALIDATION_ERROR"
    assert post(stt_client, wav_bytes(), language="en").status_code == 422


def test_disabled_stt_is_503(client_factory: Callable[..., TestClient]) -> None:
    client = client_factory()
    response = post(client, wav_bytes())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STT_UNAVAILABLE"
    assert client.get("/api/v1/health").json()["components"]["stt"]["status"] == "disabled"


def test_duration_and_body_limits(stt_client: TestClient) -> None:
    assert post(stt_client, wav_bytes(30)).status_code == 200
    assert post(stt_client, wav_bytes(40)).status_code == 422  # 1.3 MB but > 30 s
    assert post(stt_client, wav_bytes(70)).status_code == 413  # > 2 MB body
