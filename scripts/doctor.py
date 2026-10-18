"""Print environment diagnostics (safe to share: no paths to personal data).

uv run python scripts/doctor.py
"""

from __future__ import annotations

import importlib.util
import platform
import sys

import psutil
from _common import find_tool, tool_version

ML_PACKAGES = ("onnxruntime", "torch", "mediapipe", "faster_whisper")


def line(label: str, value: str | None) -> None:
    print(f"  {label:<22} {value if value else 'not found'}")


def main() -> int:
    print("System")
    line("OS", f"{platform.system()} {platform.release()} ({platform.machine()})")
    line("Python", f"{platform.python_version()} ({sys.executable})")
    mem = psutil.virtual_memory()
    line("RAM total / available", f"{mem.total / 2**30:.1f} GB / {mem.available / 2**30:.1f} GB")

    print("Tools")
    line("uv", tool_version(["uv", "--version"]) if find_tool("uv") else None)
    node, npm = find_tool("node"), find_tool("npm")
    line("node", tool_version([node, "--version"]) if node else None)
    line("npm", tool_version([npm, "--version"]) if npm else None)
    line("git", tool_version(["git", "--version"]) if find_tool("git") else None)

    print("GPU")
    smi = find_tool("nvidia-smi")
    query = "--query-gpu=name,memory.total,memory.used,memory.free"
    gpu = tool_version([smi, query, "--format=csv,noheader"]) if smi else None
    line("nvidia-smi", gpu or ("not found (expected on the Mac)" if not smi else None))

    print("ML packages (none expected in Phase 1; never on the M1 Mac)")
    for name in ML_PACKAGES:
        line(name, "installed" if importlib.util.find_spec(name) else "not installed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
