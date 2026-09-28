"""Observability — Langfuse + OpenTelemetry tracing.

Disabled by default. When `LANGFUSE_ENABLED=true` and credentials are
present, the app installs the `openinference-instrumentation-claude-agent-sdk`
instrumentor and creates an app-level `rule-build` span per request.

The actual instrumentor import is lazy so the package is optional at
test time.
"""

from __future__ import annotations

from typing import Any

from app.config import load_settings
from app.logging import get_logger


_log = get_logger(__name__)


def configure_langfuse() -> None:
    """Install Langfuse + Claude SDK instrumentation if enabled.

    TODO: implement the lazy import + setup. Should be safe to call
    multiple times.
    """

    settings = load_settings()
    if not settings.langfuse_enabled:
        _log.info("langfuse_disabled")
        return
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        _log.warning("langfuse_enabled_but_missing_credentials")
        return
    _log.info("langfuse_configure_pending")


def langfuse_status() -> dict[str, Any]:
    """Return a non-secret status snapshot for the `/observability` route."""

    settings = load_settings()
    return {
        "enabled": settings.langfuse_enabled,
        "base_url": settings.langfuse_base_url,
        "environment": settings.langfuse_environment,
        "has_public_key": bool(settings.langfuse_public_key),
        "has_secret_key": bool(settings.langfuse_secret_key),
    }


# `observation` is a small context manager that the orchestrator uses
# inside a request. It is a no-op when Langfuse is disabled.
from contextlib import contextmanager


@contextmanager
def observation(name: str, **attrs: Any):
    """Create a span with the given name and attributes."""

    _log.info("observation_start", name=name, **attrs)
    try:
        yield _DummySpan()
    finally:
        _log.info("observation_end", name=name)


class _DummySpan:
    """Placeholder span object used when Langfuse is disabled."""

    def update(self, **kwargs: Any) -> None:
        return None


def update_observation(_span: Any, **attrs: Any) -> None:
    """Update a span with new attributes. No-op when Langfuse is off."""

    return None


def record_exception(_span: Any, exc: BaseException) -> None:
    """Record an exception on the current span."""

    _log.error("observation_exception", error=str(exc))
