"""Pytest fixtures."""
from __future__ import annotations

from pathlib import Path
import pytest
from app.config import load_settings
from app.tools.config_loader import reload_configs


@pytest.fixture(autouse=True)
def _clear_cache():
    reload_configs()


@pytest.fixture
def settings():
    return load_settings()


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
