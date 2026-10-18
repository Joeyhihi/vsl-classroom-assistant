"""scripts/fetch_mediapipe_assets.py: zip detection and Windows-safe cleanup (no network)."""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import fetch_mediapipe_assets as fetch

URL = "https://storage.googleapis.com/mediapipe-models/x/x.task"


def task_bytes(prefix: bytes = b"\x00\x00\x00\x00") -> bytes:
    """A zip with leading bytes, like MediaPipe's real .task files."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("model.tflite", b"\x01" * 64)
    return prefix + buffer.getvalue()


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def serve(monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(body))


def test_real_task_layout_with_leading_bytes_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "x.task"
    path.write_bytes(task_bytes())
    assert fetch.is_task_file(path)


def test_html_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "x.task"
    path.write_bytes(b"<!doctype html><html></html>")
    assert not fetch.is_task_file(path)


def test_download_moves_a_valid_file_into_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, task_bytes())
    dest = tmp_path / "x.task"
    digest = fetch.download(URL, dest)
    assert dest.read_bytes() == task_bytes() and len(digest) == 64
    assert not (tmp_path / "x.task.part").exists()


def test_invalid_download_is_removed_after_handles_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    serve(monkeypatch, b"<html>captive portal</html>")
    opened: list[Any] = []
    real_open = Path.open

    def tracking_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        handle = real_open(self, *args, **kwargs)
        opened.append(handle)
        return handle

    real_unlink = Path.unlink

    def windows_unlink(self: Path, missing_ok: bool = False) -> None:
        # Windows semantics: deleting a file with an open handle fails (WinError 32).
        if any(not h.closed and Path(h.name) == self for h in opened):
            raise PermissionError(32, "The process cannot access the file")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "open", tracking_open)
    monkeypatch.setattr(Path, "unlink", windows_unlink)

    with pytest.raises(SystemExit, match=r"not a MediaPipe \.task"):
        fetch.download(URL, tmp_path / "x.task")
    assert list(tmp_path.iterdir()) == []


def test_remove_retries_while_antivirus_holds_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "locked.task"
    path.write_bytes(b"x")
    attempts = {"n": 0}
    real_unlink = Path.unlink

    def flaky_unlink(self: Path, missing_ok: bool = False) -> None:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise PermissionError(32, "locked")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    monkeypatch.setattr("time.sleep", lambda _s: None)

    fetch.remove(path)
    assert attempts["n"] == 3 and not path.exists()


def test_remove_gives_up_after_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def always_locked(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(32, "locked")

    monkeypatch.setattr(Path, "unlink", always_locked)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    with pytest.raises(PermissionError):
        fetch.remove(tmp_path / "x")


def test_oversized_download_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    serve(monkeypatch, task_bytes())
    monkeypatch.setattr(fetch, "MAX_BYTES", 10)
    with pytest.raises(SystemExit, match="larger than"):
        fetch.download(URL, tmp_path / "x.task")
    assert list(tmp_path.iterdir()) == []
