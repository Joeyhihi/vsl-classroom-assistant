"""Start ONLY the frontend (ADR-016: no combined launcher).

uv run python scripts/run_web.py             # Vite dev server
uv run python scripts/run_web.py --preview   # build, then serve the built app (lower RAM)
"""

from __future__ import annotations

import argparse
import sys

from _common import WEB_DIR, require_tool, run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="serve the production build")
    parser.add_argument("--port", type=int, default=5173)
    args = parser.parse_args()

    npm = require_tool("npm", "Install Node 24 LTS (see .nvmrc).")
    if not (WEB_DIR / "node_modules").exists():
        sys.exit("error: apps/web/node_modules missing. Run: uv run python scripts/bootstrap.py")

    try:
        if args.preview:
            if run([npm, "run", "build"], cwd=WEB_DIR) != 0:
                return 1
            return run([npm, "run", "preview", "--", "--port", str(args.port)], cwd=WEB_DIR)
        return run([npm, "run", "dev", "--", "--port", str(args.port)], cwd=WEB_DIR)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
