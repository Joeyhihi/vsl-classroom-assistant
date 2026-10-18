"""Start the whole app with one command (P9 packaging): build the web app, then serve
it from the backend on one origin. For classroom / pilot use, not development.

    uv run --extra windows python scripts/run_app.py      # Windows laptop (real models)
    uv run python scripts/run_app.py --mock               # demo with scripted predictions
    uv run python scripts/run_app.py --no-build           # reuse apps/web/dist

Then open http://127.0.0.1:8000 in Chrome (opened automatically unless --no-open).
Development still uses run_backend.py + run_web.py in two terminals (ADR-016).
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser

from _common import REPO_ROOT, WEB_DIR, require_tool, run


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--mock", action="store_true", help="dev + mock model mode")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-build", action="store_true", help="serve the existing build")
    parser.add_argument("--no-open", action="store_true", help="do not open the browser")
    args = parser.parse_args()

    dist = WEB_DIR / "dist"
    if not args.no_build:
        npm = require_tool("npm", "Install Node 24 LTS (see .nvmrc).")
        if not (WEB_DIR / "node_modules").exists():
            sys.exit(
                "error: apps/web/node_modules missing. Run: uv run python scripts/bootstrap.py"
            )
        # One origin: the app talks to /api on the server that serves it
        # (process env wins over .env files in Vite).
        os.environ["VITE_API_BASE"] = "/api/v1"
        if run([npm, "run", "build"], cwd=WEB_DIR) != 0:
            return 1
    if not (dist / "index.html").is_file():
        sys.exit("error: apps/web/dist is missing; run without --no-build")

    os.environ["VSL_SERVE_WEB"] = "true"
    os.environ["VSL_WEB_DIST_DIR"] = str(dist)
    os.environ["VSL_PORT"] = str(args.port)
    if args.mock:
        os.environ["VSL_ENV"] = "dev"
        os.environ["VSL_MODEL_MODE"] = "mock"
    os.chdir(REPO_ROOT)  # .env is read from the repository root

    import uvicorn
    from pydantic import ValidationError

    from vsl_backend.config import Settings

    try:
        settings = Settings()
    except ValidationError as exc:
        print(f"error: invalid configuration:\n{exc}", file=sys.stderr)
        return 2

    url = f"http://127.0.0.1:{settings.port}/"
    print(f"VSL Classroom Assistant: {url}  (mode={settings.model_mode}; Ctrl+C to stop)")
    if not args.no_open:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(
        "vsl_backend.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
