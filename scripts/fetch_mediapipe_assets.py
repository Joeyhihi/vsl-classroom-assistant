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
import urllib.request
from pathlib import Path

from _common import REPO_ROOT, WEB_DIR

MANIFEST = REPO_ROOT / "scripts" / "mediapipe_assets.json"
TARGET = WEB_DIR / "public" / "mediapipe"
WASM_SOURCE = WEB_DIR / "node_modules" / "@mediapipe" / "tasks-vision" / "wasm"
MAX_BYTES = 100 * 1024 * 1024
ZIP_MAGIC = b"PK\x03\x04"  # .task files are zip archives


def download(url: str, dest: Path) -> str:
    if not url.startswith("https://storage.googleapis.com/mediapipe-models/"):
        sys.exit(f"error: refusing unexpected model URL {url}")
    digest = hashlib.sha256()
    size = 0
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=60) as response, tmp.open("wb") as out:
        while chunk := response.read(1 << 16):
            size += len(chunk)
            if size > MAX_BYTES:
                tmp.unlink(missing_ok=True)
                sys.exit(f"error: {dest.name} is larger than {MAX_BYTES // 2**20} MB")
            digest.update(chunk)
            out.write(chunk)
    with tmp.open("rb") as check:
        if check.read(4) != ZIP_MAGIC:  # e.g. an HTML error page or captive portal
            tmp.unlink()
            sys.exit(f"error: {dest.name} is not a MediaPipe .task (zip) file")
    tmp.replace(dest)
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
                (TARGET / name).unlink()
                sys.exit(f"error: {name} has no pinned sha256; rerun with --pin, then commit")
            entry["sha256"] = digest
            changed = True
            print(f"  pinned sha256 {digest}")
        elif entry["sha256"] != digest:
            (TARGET / name).unlink()
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
