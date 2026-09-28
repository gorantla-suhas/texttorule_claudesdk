"""Logging configuration.

Wires `structlog` so the same JSON output goes to stdout and to the
`logs/` directory. The hooks module and the tools call
`get_logger(__name__)` to get a bound, context-aware logger.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog

from app.config import PROJECT_DIR, load_settings


_LOG_DIR: Path = PROJECT_DIR / "logs"


def configure_logging() -> None:
    """Configure stdlib logging + structlog. Call once at startup."""

    settings = load_settings()
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(message)s",
        stream=sys.stdout,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger for the given module name."""

    return structlog.get_logger(name)
