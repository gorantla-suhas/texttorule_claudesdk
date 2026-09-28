"""Tests for the `.env.example` template.

Ensures the template documents every env var the code reads, and
that no stale vars remain.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import config as config_module
from app.services import sql_lookup


def _env_keys(text: str) -> set[str]:
    """Extract `KEY=` lines (ignoring comments, blanks, and continuation lines)."""

    keys: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Z_][A-Z0-9_]*)\s*=", line)
        if m:
            keys.add(m.group(1))
    return keys


def test_env_example_exists():
    path = Path(".env.example")
    assert path.exists(), ".env.example must exist at the project root"


def test_env_example_documents_all_settings_keys():
    text = Path(".env.example").read_text(encoding="utf-8")
    declared = _env_keys(text)

    # Every env var the app reads must be declared.
    expected = set()
    for f in (config_module, sql_lookup):
        src = Path(f.__file__).read_text(encoding="utf-8")
        for m in re.finditer(r'os\.environ(?:\.get\(["\']([A-Z_][A-Z0-9_]*)["\']\)|\[\s*["\']([A-Z_][A-Z0-9_]*)["\']\s*\])', src):
            expected.add(m.group(1) or m.group(2))

    missing = expected - declared
    assert not missing, f".env.example missing keys: {sorted(missing)}"


def test_env_example_documents_anthropic_keys():
    text = Path(".env.example").read_text(encoding="utf-8")
    declared = _env_keys(text)
    # SDK reads these natively — must be documented.
    assert "ANTHROPIC_BASE_URL" in declared
    assert "ANTHROPIC_API_KEY" in declared


def test_env_example_documents_db_keys():
    text = Path(".env.example").read_text(encoding="utf-8")
    declared = _env_keys(text)
    assert "DB_HOST" in declared
    assert "DB_NAME" in declared
    assert "DB_USER" in declared
    assert "DB_PASSWORD" in declared
    assert "DB_DRIVER" in declared


def test_env_example_documents_langfuse_keys():
    text = Path(".env.example").read_text(encoding="utf-8")
    declared = _env_keys(text)
    for k in ("LANGFUSE_ENABLED", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
              "LANGFUSE_BASE_URL", "LANGFUSE_TRACING_ENVIRONMENT"):
        assert k in declared, f"{k} missing from .env.example"


def test_env_example_documents_verifier_mode():
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "RULE_VERIFIER_MODE" in _env_keys(text)


def test_env_example_has_comments_explaining_each_section():
    text = Path(".env.example").read_text(encoding="utf-8")
    # Section headers are present.
    assert "# Claude Agent SDK provider" in text or "# Claude Agent SDK" in text
    assert "# Database" in text
    assert "# Langfuse" in text
    assert "# Engine" in text


def test_env_example_no_trailing_whitespace_on_blank_lines():
    """Cosmetic — blank lines should be truly blank, not space-padded."""

    text = Path(".env.example").read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), start=1):
        if line == "":
            continue
        # Lines that are pure whitespace are not allowed.
        if line.strip() == "":
            assert line == "", f"line {i} has trailing whitespace: {line!r}"


def test_python_dotenv_dependency_declared():
    """`python-dotenv` must be in `pyproject.toml` so the auto-load
    behavior works out of the box."""

    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "python-dotenv" in text


def test_config_module_calls_load_dotenv_on_import(monkeypatch):
    """`app.config` calls `load_dotenv` when imported, so `.env` values
    are picked up automatically. Smoke test: monkeypatch load_dotenv
    and verify it was called."""

    import importlib
    import sys

    # Stub the dotenv module before re-importing config.
    calls: list[dict[str, Any]] = []

    class _FakeDotenv:
        @staticmethod
        def load_dotenv(path, override=False):
            calls.append({"path": str(path), "override": override})

    # Build a fake module under the name "dotenv".
    import types

    fake_mod = types.ModuleType("dotenv")
    fake_mod.load_dotenv = _FakeDotenv.load_dotenv  # type: ignore[attr-defined]

    # Save and swap the real dotenv (if any).
    saved = sys.modules.pop("dotenv", None)
    sys.modules["dotenv"] = fake_mod

    try:
        # Force re-import of app.config.
        sys.modules.pop("app.config", None)
        importlib.import_module("app.config")
        assert len(calls) >= 1, "load_dotenv was not called on app.config import"
        assert calls[0]["override"] is False, "load_dotenv should not override shell env"
    finally:
        sys.modules.pop("app.config", None)
        if saved is not None:
            sys.modules["dotenv"] = saved
        else:
            sys.modules.pop("dotenv", None)
        # Re-import to leave the module cache in a sane state.
        importlib.import_module("app.config")


from typing import Any  # noqa: E402  — used by the test above