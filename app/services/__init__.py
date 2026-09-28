"""Pure-Python infrastructure services.

These modules contain no business logic and no LLM calls. They are
the deterministic helpers that the MCP tools and tests call into.
"""

from app.services.csv_loader import load_kpi_csv, load_kpi_catalog
from app.services.embedding import build_bm25_index, build_embedding_matrix
from app.services.persistence import (
    append_audit_record,
    load_audit_log,
    save_rule,
)


__all__ = [
    "load_kpi_csv",
    "load_kpi_catalog",
    "build_bm25_index",
    "build_embedding_matrix",
    "append_audit_record",
    "load_audit_log",
    "save_rule",
]