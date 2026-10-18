"""Logging setup.

Policy (docs/SECURITY_AND_PRIVACY.md): log counts, latencies, status/error codes
and request ids only — never landmarks, frames, audio, transcript text or
feedback content.
"""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT)
    logging.getLogger("vsl_backend").setLevel(level)
