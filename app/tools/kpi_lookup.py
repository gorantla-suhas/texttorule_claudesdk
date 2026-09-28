"""KPI catalog loader.

Reads `data/kpis.csv` into a list of
`KpiMeta` records. Used by `vector_search` and `validate_rule` to
confirm column existence and to read column metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class KpiMeta:
    """One row of the canonical KPI catalog."""

    id: str
    feature_name: str
    group_id: str
    group_name: str
    kpi_type: str
    description: str
    kpi_type_name: str
    time_window_value: str
    activity: str
    network_scope: str
    direction_value: str
    data_type: str
    value_references: str
    value_type: str
    aliases: str
    search_text: str


def load_kpi_catalog(csv_path: Path) -> list[KpiMeta]:
    """Load the KPI catalog from a CSV file.

    TODO: implement via pandas; for now returns an empty list so the
    import surface is stable.
    """

    if not csv_path.exists():
        return []
    return _read_csv(csv_path)


def _read_csv(csv_path: Path) -> list[KpiMeta]:
    """Internal: read + parse the CSV into `KpiMeta` records."""

    # Implementation deferred; see `load_kpi_catalog`.
    return []


def known_columns(catalog: Iterable[KpiMeta]) -> set[str]:
    """Return the set of `column_name` values in the catalog."""

    return {row.feature_name for row in catalog}
