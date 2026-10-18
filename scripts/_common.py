"""Small helpers shared by the scripts in this folder (stdlib only)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "apps" / "web"


def find_tool(name: str) -> str | None:
    """Resolve an executable; on Windows this finds `npm.cmd` etc."""
    return shutil.which(name)


def require_tool(name: str, hint: str) -> str:
    path = find_tool(name)
    if path is None:
        sys.exit(f"error: '{name}' not found on PATH. {hint}")
    return path


def run(cmd: Sequence[str], cwd: Path = REPO_ROOT) -> int:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.call(list(cmd), cwd=cwd)


def tool_version(cmd: Sequence[str]) -> str | None:
    try:
        out = subprocess.run(list(cmd), capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or out.stderr.strip()
