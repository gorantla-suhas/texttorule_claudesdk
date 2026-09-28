"""Bonus catalog lookup."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def lookup_bonus(bonus_type: str, client: str, audience: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Search the client bonus catalog.

    TODO: implement against `data/sdk_context/catalogs/bonuses_<client>.json`.
    """

    return []


def load_bonuses(json_path: Path) -> list[dict[str, Any]]:
    """Load the bonus catalog from disk (used by tests)."""

    if not json_path.exists():
        return []
    return []
