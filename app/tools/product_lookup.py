"""Product catalog lookup."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def lookup_product(query: str, client: str, family: str | None = None) -> list[dict[str, Any]]:
    """Search the client product catalog.

    TODO: implement against `data/sdk_context/catalogs/products_<client>.json`.
    For now returns an empty list so the import surface is stable.
    """

    return []


def load_products(json_path: Path) -> list[dict[str, Any]]:
    """Load the product catalog from disk (used by tests)."""

    if not json_path.exists():
        return []
    return _read_json(json_path)


def _read_json(path: Path) -> list[dict[str, Any]]:
    """Internal: read + parse the JSON file."""

    return []
