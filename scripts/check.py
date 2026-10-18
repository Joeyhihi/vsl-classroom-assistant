"""Run every local quality gate (same as CI, minus gitleaks).

    uv run python scripts/check.py [--skip-web] [--skip-python] [--skip-e2e]

Needs no webcam, GPU or ML model (docs/TESTING_STRATEGY.md).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from _common import REPO_ROOT, WEB_DIR, require_tool, run

PY = sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-web", action="store_true")
    parser.add_argument("--skip-python", action="store_true")
    parser.add_argument("--skip-e2e", action="store_true", help="skip Playwright (needs Chrome)")
    args = parser.parse_args()

    steps: list[tuple[str, list[str], Path]] = [
        ("guard_no_media", [PY, "scripts/guard_no_media.py"], REPO_ROOT),
    ]
    if not args.skip_python:
        steps += [
            ("ruff check", [PY, "-m", "ruff", "check", "."], REPO_ROOT),
            ("ruff format", [PY, "-m", "ruff", "format", "--check", "."], REPO_ROOT),
            ("mypy", [PY, "-m", "mypy"], REPO_ROOT),
            ("pytest", [PY, "-m", "pytest"], REPO_ROOT),
        ]
    if not args.skip_web:
        npm = require_tool("npm", "Install Node 24 LTS or pass --skip-web.")
        steps += [
            ("web lint", [npm, "run", "lint"], WEB_DIR),
            ("web typecheck", [npm, "run", "typecheck"], WEB_DIR),
            ("web test", [npm, "test"], WEB_DIR),
            ("web build", [npm, "run", "build"], WEB_DIR),
        ]
        if not args.skip_e2e:
            steps.append(("web e2e", [npm, "run", "e2e"], WEB_DIR))

    results: list[tuple[str, bool, float]] = []
    for name, cmd, cwd in steps:
        print(f"\n=== {name} ===", flush=True)
        start = time.monotonic()
        ok = run(cmd, cwd=cwd) == 0
        results.append((name, ok, time.monotonic() - start))

    print("\n=== summary ===")
    for name, ok, seconds in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<16} {seconds:5.1f}s")
    failed = [name for name, ok, _ in results if not ok]
    print(f"\n{'All gates passed.' if not failed else 'Failed: ' + ', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
