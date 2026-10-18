"""Typed application settings, read from environment variables and `.env`.

See docs/CROSS_PLATFORM_SETUP.md §5 for every variable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from platformdirs import user_data_dir
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

Environment = Literal["dev", "prod"]
ModelMode = Literal["mock", "template", "onnx"]
MockScript = Literal["cycle", "timer"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VSL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Environment = "dev"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_mode: ModelMode = "mock"
    mock_script: MockScript = "cycle"
    sign_model_id: str | None = None

    model_artifacts_dir: Path = Path("model-artifacts")
    data_root: Path | None = None
    stt_enabled: bool = False

    # L3 server-side extraction (ADR-002). Needs the `server-extraction` extra and
    # the Holistic model fetched by `bootstrap.py --with-models` (Windows only).
    server_extraction_enabled: bool = False
    holistic_model_path: Path = Path("apps/web/public/mediapipe/holistic_landmarker.task")

    # Recognition WebSocket limits (docs/API_CONTRACTS.md).
    max_session_s: int = Field(default=7200, gt=0)
    max_fps: int = Field(default=30, gt=0)
    max_fps_server_extraction: int = Field(default=20, gt=0)
    max_batch: int = Field(default=8, gt=0)
    ws_max_message_bytes: int = Field(default=64 * 1024, gt=0)
    ws_max_binary_bytes: int = Field(default=200 * 1024, gt=0)
    heartbeat_timeout_s: float = Field(default=15.0, gt=0)
    cooldown_ms: float = Field(default=1500.0, ge=0)

    # Phase 4 recorder (developer self-recording). Off by default; data goes to
    # DATA_ROOT, never into the repository.
    recorder_enabled: bool = False
    # Recording other people stays blocked until the consent package (B2) is
    # approved; do not enable before that (docs/DATASET_AND_ANNOTATION.md §3).
    third_party_recording_enabled: bool = False
    dev_vocabulary_path: Path = Path("ml/vocabulary/vocabulary.dev.json")
    recording_max_body_bytes: int = Field(default=2 * 1024 * 1024, gt=0)

    # ResourceManager (ADR-015): heavy engines (STT from P7) only.
    heavy_model_idle_unload_s: float = Field(default=300.0, gt=0)
    min_free_ram_mb: float = Field(default=1500.0, ge=0)
    resource_sweep_interval_s: float = Field(default=30.0, gt=0)

    max_body_bytes: int = Field(default=64 * 1024, gt=0)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @model_validator(mode="after")
    def _check_safety(self) -> Settings:
        # ADR-016: scripted predictions must never reach a real (non-dev) setting.
        if self.model_mode == "mock" and self.env != "dev":
            raise ValueError("mock model mode requires VSL_ENV=dev")
        # ADR-006: local-first; never listen on a network interface.
        if self.host not in LOOPBACK_HOSTS:
            raise ValueError(f"VSL_HOST must be a loopback address, got {self.host!r}")
        if self.sign_model_id == "":
            self.sign_model_id = None
        return self

    @property
    def allowed_origin_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def resolved_data_root(self) -> Path:
        """Research data, feedback and reports. Always outside the repository."""
        if self.data_root is not None:
            return self.data_root.expanduser()
        return Path(user_data_dir("vsl-classroom-assistant", appauthor=False))
