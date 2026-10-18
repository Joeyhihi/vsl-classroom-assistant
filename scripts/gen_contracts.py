"""Generate TypeScript types from the Pydantic API schemas (single source of truth).

uv run python scripts/gen_contracts.py           # write apps/web/src/api/generated/contracts.ts
uv run python scripts/gen_contracts.py --check   # fail if the committed file is stale (CI)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from _common import REPO_ROOT, WEB_DIR, require_tool
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from vsl_backend.api.v1.models import DiagnosticsResponse
from vsl_backend.schemas.common import ErrorResponse
from vsl_backend.schemas.health import HealthResponse
from vsl_backend.schemas.recognition import (
    ErrorMessage,
    FramesBatchContract,
    ModelInfo,
    Ping,
    PredictionMessage,
    SessionStart,
    SessionStarted,
    SessionStop,
    SessionStopped,
    StatusMessage,
    VocabularyResponse,
)
from vsl_backend.schemas.recognition import Pong as PongMessage

OUTPUT = WEB_DIR / "src" / "api" / "generated" / "contracts.ts"

MODELS: list[type[BaseModel]] = [
    HealthResponse,
    ErrorResponse,
    VocabularyResponse,
    ModelInfo,
    DiagnosticsResponse,
    SessionStart,
    FramesBatchContract,
    SessionStop,
    Ping,
    SessionStarted,
    StatusMessage,
    PredictionMessage,
    ErrorMessage,
    SessionStopped,
    PongMessage,
]


def _strip_titles(node: object, keep: bool) -> object:
    """Drop per-property titles so json2ts emits inline types, not one alias per field."""
    if isinstance(node, dict):
        return {
            k: _strip_titles(v, keep=False)
            for k, v in node.items()
            if not (k == "title" and not keep and isinstance(v, str))
        }
    if isinstance(node, list):
        return [_strip_titles(v, keep=False) for v in node]
    return node


def schema() -> dict[str, object]:
    _, top = models_json_schema([(m, "serialization") for m in MODELS], title="Contracts")
    defs = {name: _strip_titles(d, keep=True) for name, d in top["$defs"].items()}
    return {
        "title": "Contracts",
        "type": "object",
        "properties": {m.__name__: {"$ref": f"#/$defs/{m.__name__}"} for m in MODELS},
        "$defs": defs,
    }


def render() -> str:
    node = require_tool("node", "Install Node 24 LTS (see .nvmrc).")
    result = subprocess.run(
        [node, str(WEB_DIR / "scripts" / "json2ts.mjs")],
        input=json.dumps(schema(), sort_keys=True),
        capture_output=True,
        text=True,
        cwd=WEB_DIR,
        check=True,
        encoding="utf-8",
    )
    return result.stdout.replace("\r\n", "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = render()
    rel = OUTPUT.relative_to(REPO_ROOT)
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            print(f"{rel} is stale. Run: uv run python scripts/gen_contracts.py")
            return 1
        print("contracts: up to date")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
