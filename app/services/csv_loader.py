"""CSV loader for the KPI catalog.

Pure pandas wrapper. The loader is the single point that knows how to
turn a KPI CSV row into a `KpiMeta` dataclass. The retriever and the
validator both call into here so they share the same row shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pandas as pd

from app.tools.kpi_lookup import KpiMeta


_KPI_COLUMNS = [
    "id",
    "feature_name",
    "group_id",
    "group_name",
    "kpi_type",
    "description",
    "kpi_type_name",
    "time_window_value",
    "activity",
    "network_scope",
    "direction_value",
    "data_type",
    "value_references",
    "value_type",
    "aliases",
    "search_text",
]


def load_kpi_csv(csv_path: Path) -> pd.DataFrame:
    """Load the KPI CSV into a pandas DataFrame.

    TODO: implement the actual read with explicit dtype handling. For
    now this is a thin wrapper so the import surface is stable.
    """

    return pd.read_csv(csv_path, dtype=str, keep_default_na=False)


def load_kpi_catalog(csv_path: Path) -> list[KpiMeta]:
    """Read the CSV and return a list of `KpiMeta` records."""

    df = load_kpi_csv(csv_path)
    return [KpiMeta(**{col: row.get(col, "") for col in _KPI_COLUMNS}) for _, row in df.iterrows()]


def iter_kpis(csv_path: Path, batch_size: int = 500) -> Iterator[list[KpiMeta]]:
    """Stream the catalog in batches (used by the indexer)."""

    catalog = load_kpi_catalog(csv_path)
    for i in range(0, len(catalog), batch_size):
        yield catalog[i : i + batch_size]
