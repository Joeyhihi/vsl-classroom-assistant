"""Install project dependencies on macOS or Windows.

    uv run python scripts/bootstrap.py

Never downloads ML models. `--with-models` (Windows only, Phase 3+) will fetch
pinned MediaPipe assets; see docs/CROSS_PLATFORM_SETUP.md.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import sys

from _common import REPO_ROOT, WEB_DIR, require_tool, run, tool_version

MIN_NODE_MAJOR = 24


def check_node(node: str) -> None:
    version = tool_version([node, "--version"]) or "v0"
    major = int(version.lstrip("v").split(".")[0] or 0)
    if major < MIN_NODE_MAJOR:
        print(f"warning: Node {version} found; Node {MIN_NODE_MAJOR} LTS is expected (.nvmrc).")


def ensure_env_file() -> None:
    env, example = REPO_ROOT / ".env", REPO_ROOT / ".env.example"
    if env.exists():
        print(".env exists — left unchanged")
    else:
        shutil.copyfile(example, env)
        print("created .env from .env.example")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-models", action="store_true", help="fetch model assets (P3+)")
    parser.add_argument("--skip-web", action="store_true", help="skip npm install")
    args = parser.parse_args()

    if args.with_models:
        if platform.system() == "Darwin":
            sys.exit("error: model assets are never downloaded on the Mac (M1 mock-only rule).")
        sys.exit("error: --with-models is not available until Phase 3.")

    uv = require_tool("uv", "Install uv: https://docs.astral.sh/uv/")
    ensure_env_file()
    if run([uv, "sync"]) != 0:
        return 1

    if not args.skip_web:
        node = require_tool("node", "Install Node 24 LTS (see .nvmrc).")
        npm = require_tool("npm", "npm ships with Node.")
        check_node(node)
        has_lock = (WEB_DIR / "package-lock.json").exists()
        if run([npm, "ci" if has_lock else "install"], cwd=WEB_DIR) != 0:
            return 1

    print("\nBootstrap complete. Next:")
    print("  uv run python scripts/run_backend.py   # terminal 1")
    print("  uv run python scripts/run_web.py       # terminal 2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
