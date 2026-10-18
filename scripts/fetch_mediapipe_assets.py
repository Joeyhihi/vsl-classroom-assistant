"""Fetch self-hosted MediaPipe assets for L1/L2/L3 (Windows laptop only).

    uv run python scripts/fetch_mediapipe_assets.py          # verify pinned sha256
    uv run python scripts/fetch_mediapipe_assets.py --pin    # first run: record sha256

Copies the tasks-vision WASM runtime from node_modules and downloads the model
files into apps/web/public/mediapipe/ (gitignored). Never runs on macOS: the M1
development Mac must not download or run models (docs/CROSS_PLATFORM_SETUP.md).

Trust on first use: the first `--pin` run writes the sha256 of each model into
scripts/mediapipe_assets.json; commit that file so later fetches are verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import time
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from _common import REPO_ROOT, WEB_DIR

MANIFEST = REPO_ROOT / "scripts" / "mediapipe_assets.json"
TARGET = WEB_DIR / "public" / "mediapipe"
WASM_SOURCE = WEB_DIR / "node_modules" / "@mediapipe" / "tasks-vision" / "wasm"
MAX_BYTES = 100 * 1024 * 1024
RETRIES = 5
RETRY_DELAY_S = 0.2


def is_task_file(path: Path) -> bool:
    """.task files are zip archives, but may have bytes BEFORE the zip header
    (MediaPipe's start with 2-4 zero bytes), so check the end-of-central-directory
    record like any zip reader does, not the first bytes."""
    return zipfile.is_zipfile(path)


def _retry(action: Callable[[], object], what: str) -> None:
    """On Windows, antivirus scanners briefly lock newly written files."""
    for attempt in range(RETRIES):
        try:
            action()
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == RETRIES - 1:
                raise
            time.sleep(RETRY_DELAY_S * (attempt + 1))
    raise AssertionError(f"unreachable: {what}")


def remove(path: Path) -> None:
    _retry(lambda: path.unlink(missing_ok=True), f"remove {path}")


def replace(src: Path, dest: Path) -> None:
    _retry(lambda: src.replace(dest), f"replace {dest}")


def download(url: str, dest: Path) -> str:
    """Download to a temp file, verify it, then move it into place.

    Every file handle is closed before the file is removed or renamed: Windows
    cannot delete or rename a file that is still open (WinError 32).
    """
    if not url.startswith("https://storage.googleapis.com/mediapipe-models/"):
        sys.exit(f"error: refusing unexpected model URL {url}")
    digest = hashlib.sha256()
    size = 0
    too_large = False
    tmp = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=60) as response, tmp.open("wb") as out:
        while chunk := response.read(1 << 16):
            size += len(chunk)
            if size > MAX_BYTES:
                too_large = True
                break
            digest.update(chunk)
            out.write(chunk)
    # Both handles are closed here.
    if too_large:
        remove(tmp)
        sys.exit(f"error: {dest.name} is larger than {MAX_BYTES // 2**20} MB")
    if not is_task_file(tmp):  # e.g. an HTML error page or captive portal
        remove(tmp)
        sys.exit(f"error: {dest.name} is not a MediaPipe .task (zip) file")
    replace(tmp, dest)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--pin", action="store_true", help="record sha256 for unpinned models")
    args = parser.parse_args()

    if platform.system() == "Darwin":
        sys.exit("error: MediaPipe models are never downloaded on the Mac (M1 mock-only rule).")
    if not WASM_SOURCE.is_dir():
        sys.exit("error: node_modules missing; run scripts/bootstrap.py first")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    TARGET.mkdir(parents=True, exist_ok=True)
    shutil.copytree(WASM_SOURCE, TARGET / "wasm", dirs_exist_ok=True)
    print(f"copied WASM runtime (tasks-vision {manifest['tasks_vision_version']})")

    changed = False
    for name, entry in manifest["models"].items():
        print(f"downloading {name} …")
        digest = download(entry["url"], TARGET / name)
        if entry["sha256"] is None:
            if not args.pin:
                remove(TARGET / name)
                sys.exit(f"error: {name} has no pinned sha256; rerun with --pin, then commit")
            entry["sha256"] = digest
            changed = True
            print(f"  pinned sha256 {digest}")
        elif entry["sha256"] != digest:
            remove(TARGET / name)
            sys.exit(f"error: sha256 mismatch for {name}; review the upstream change first")
        else:
            print("  sha256 verified")

    print(f"\nAssets are in {TARGET.relative_to(REPO_ROOT)} (served at /mediapipe/).")
    print("If you use run_web.py --preview, it rebuilds and copies them into dist/ automatically.")
    if changed:
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(f"\nUpdated {MANIFEST.relative_to(REPO_ROOT)}; commit it to verify later fetches.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
