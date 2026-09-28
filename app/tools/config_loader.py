"""YAML configuration loader.

Reads `configs/*.yaml` and returns typed-ish dicts. The orchestrator
and the tools call `load_config(name)` to get a single file. The
loader caches reads per process.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.config import CONFIGS_DIR


@lru_cache(maxsize=None)
def load_config(name: str) -> dict:
    """Load a single YAML config file by short name.

    `name` is the file stem (e.g. `"action_catalog"` reads
    `configs/action_catalog.yaml`).
    """

    path: Path = CONFIGS_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def reload_configs() -> None:
    """Clear the cache. Useful for tests that write new fixtures."""

    load_config.cache_clear()
