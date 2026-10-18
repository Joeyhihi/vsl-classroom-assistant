"""Start ONLY the backend (ADR-016: no combined launcher).

uv run python scripts/run_backend.py          # settings from .env
uv run python scripts/run_backend.py --mock   # force dev + mock model mode
"""

from __future__ import annotations

import argparse
import os
import sys

from _common import REPO_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock", action="store_true", help="force dev + mock mode")
    parser.add_argument("--port", type=int, help="override VSL_PORT")
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    args = parser.parse_args()

    if args.mock:
        os.environ["VSL_ENV"] = "dev"
        os.environ["VSL_MODEL_MODE"] = "mock"
    if args.port:
        os.environ["VSL_PORT"] = str(args.port)

    os.chdir(REPO_ROOT)  # .env is read from the repository root

    import uvicorn
    from pydantic import ValidationError

    from vsl_backend.config import Settings

    try:
        settings = Settings()
    except ValidationError as exc:
        print(f"error: invalid configuration:\n{exc}", file=sys.stderr)
        return 2

    print(f"backend: http://{settings.host}:{settings.port}  mode={settings.model_mode}")
    if settings.server_extraction_enabled:
        from vsl_backend.extraction.server_extractor import extraction_unavailable_reason

        reason = extraction_unavailable_reason(True, settings.holistic_model_path)
        if reason:
            # `uv run` / `uv sync` without --extra removes the optional packages again.
            print(f"WARNING: L3 server extraction unavailable: {reason}", file=sys.stderr)
            print(
                "  start with: uv run --extra server-extraction python scripts/run_backend.py",
                file=sys.stderr,
            )
        else:
            print("L3 server extraction: available")
    uvicorn.run(
        "vsl_backend.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=args.reload,
        reload_dirs=[str(REPO_ROOT / "services" / "ai-backend" / "src")] if args.reload else None,
        log_level=settings.log_level.lower(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
