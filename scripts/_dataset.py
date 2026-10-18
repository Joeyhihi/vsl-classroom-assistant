"""Shared helper for dataset scripts: resolve DATA_ROOT the same way the backend does."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from _common import REPO_ROOT

from vsl_features.dataset import DatasetError, ensure_outside_repo


def resolve_data_root(arg: Path | None) -> Path:
    if arg is None:
        os.chdir(REPO_ROOT)  # .env lives at the repository root
        from vsl_backend.config import Settings

        root = Settings().resolved_data_root
    else:
        root = arg.expanduser()
    try:
        ensure_outside_repo(root)
    except DatasetError as exc:
        sys.exit(f"error: {exc}")
    return root
