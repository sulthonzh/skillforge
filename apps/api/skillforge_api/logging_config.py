"""Unified logging configuration for SkillForge.

One format for every logger: uvicorn access logs, httpx outbound requests, and
the app's own code. Without this, the console shows three different formats
interleaved:

    INFO:     127.0.0.1:56979 - "GET /api/... HTTP/1.1" 200 OK      <- uvicorn
    2026-06-18 08:24:36,913 INFO httpx: HTTP Request: POST ...       <- httpx
    2026-06-18 08:30:00,000 INFO skillforge_api: serving...           <- app

The cause: uvicorn installs its OWN log config (its own formatters/handlers on
the `uvicorn` and `uvicorn.access` loggers) which bypasses the root logger's
format. httpx and app code use the root logger. So we need a single
``dictConfig`` that uvicorn accepts via ``log_config=`` AND that configures the
root logger the same way — then everything flows through one formatter.

The unified format:

    2026-06-18 08:30:00.123 INFO  uvicorn.access  127.0.0.1:57038 GET /api/eval/suites 200
    2026-06-18 08:30:00.456 INFO  httpx           POST https://api.z.ai/.../chat/completions 200
    2026-06-18 08:30:00.789 INFO  skillforge_api  serving on http://127.0.0.1:8000

ISO timestamp, level, logger name (padded), then message. Consistent and greppable.
"""

from __future__ import annotations

import logging
from typing import Any

# One format string for every logger. Padded level + name columns make the
# output align into readable columns without color codes (the binary runs in a
# plain console; tests and pipes must be able to parse it).
FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-5s %(name)-14s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


def build_log_config(level: str = "INFO") -> dict[str, Any]:
    """Build a logging.config.dictConfig dict wired into uvicorn.

    Args:
        level: the minimum level for the root + uvicorn loggers.

    The returned dict configures:
      * the root logger (catches httpx, skillforge_api, and anything else)
      * the ``uvicorn`` and ``uvicorn.access`` loggers (so uvicorn's access log
        uses our format instead of its default ``INFO:     <addr> - "..."``)
      * the ``uvicorn.error`` logger (uvicorn's startup/shutdown messages)
    """
    numeric_level = _level_to_int(level)
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": FORMAT,
                "datefmt": DATEFMT,
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stderr",
                "level": "DEBUG",  # handler accepts everything; loggers filter
            },
        },
        "loggers": {
            # Root: catches httpx + app code + anything unconfigured.
            "": {
                "handlers": ["default"],
                "level": numeric_level,
            },
            # uvicorn's own startup/shutdown messages.
            "uvicorn": {
                "handlers": ["default"],
                "level": numeric_level,
                "propagate": False,  # don't double-log via root
            },
            # The access log — this is the "GET /api/... 200" line.
            "uvicorn.access": {
                "handlers": ["default"],
                "level": numeric_level,
                "propagate": False,
            },
            # uvicorn writes some errors here on startup issues.
            "uvicorn.error": {
                "handlers": ["default"],
                "level": numeric_level,
                "propagate": False,
            },
            # httpx logs every outbound HTTP request at INFO. That's useful for
            # debugging the AI provider calls but noisy in normal operation —
            # default to WARNING so the eval/chat flow stays quiet unless
            # something actually fails. Raise SKILLFORGE_HTTPX_LOG_LEVEL=INFO
            # to see every outbound call.
            "httpx": {
                "handlers": ["default"],
                "level": "WARNING",
                "propagate": False,
            },
        },
        # Apply the root level so loggers without an explicit entry inherit it.
        "root": {
            "handlers": ["default"],
            "level": numeric_level,
        },
    }


def _level_to_int(level: str) -> int:
    """Accept a level name ('INFO') or numeric string ('20')."""
    try:
        return int(level)
    except ValueError:
        return logging.getLevelName(str(level).upper())


def configure_logging(level: str = "INFO") -> None:
    """Apply the unified config to the current process (non-uvicorn entry points).

    Use this for CLI commands that don't go through uvicorn (e.g. `plan`,
    `generate`). The `serve` command passes ``build_log_config()`` to uvicorn's
    ``log_config`` instead, which applies the same config under uvicorn's
    logging setup.
    """
    import logging.config

    logging.config.dictConfig(build_log_config(level))
