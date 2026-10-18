"""Fail if media, model, dataset or oversized files would enter git (public repo).

Checks tracked files plus untracked files that are not gitignored, i.e. what
`git add -A` would stage. Synthetic fixtures under `fixtures/synthetic/` are
exempt from the extension rule (still size-limited).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import PurePosixPath

from _common import REPO_ROOT

MAX_BYTES = 1_000_000
SIZE_EXEMPT = {"uv.lock", "apps/web/package-lock.json"}
BLOCKED_SUFFIXES = {
    # models
    ".onnx", ".pt", ".pth", ".ckpt", ".task", ".tflite", ".safetensors", ".bin", ".pkl", ".pickle",
    # landmark / array data
    ".npz", ".npy", ".parquet", ".h5", ".hdf5",
    # video / audio
    ".mp4", ".mov", ".webm", ".avi", ".mkv", ".wav", ".mp3", ".flac", ".ogg", ".m4a",
}  # fmt: skip
BLOCKED_NAMES = {".env"}


def candidate_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def problems_for(path: str) -> list[str]:
    posix = PurePosixPath(path)
    found: list[str] = []
    if posix.name in BLOCKED_NAMES:
        found.append("secrets file")
    if posix.suffix.lower() in BLOCKED_SUFFIXES and "fixtures/synthetic" not in path:
        found.append(f"blocked file type {posix.suffix}")
    full = REPO_ROOT / path
    if path not in SIZE_EXEMPT and full.is_file() and full.stat().st_size > MAX_BYTES:
        found.append(f"larger than {MAX_BYTES // 1000} KB")
    return found


def main() -> int:
    failures = [(p, problems_for(p)) for p in candidate_files()]
    failures = [(p, why) for p, why in failures if why]
    for path, why in failures:
        print(f"BLOCKED {path}: {', '.join(why)}")
    if failures:
        print(f"\n{len(failures)} file(s) must not be committed (docs/SECURITY_AND_PRIVACY.md).")
        return 1
    print("guard_no_media: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
