"""Embedding + BM25 index builders.

The retriever uses a hybrid of BM25 (lexical) and a character n-gram
embedding (semantic). When `EMBEDDING_BACKEND=sentence-transformers`,
the n-gram stage is replaced with a real embedding model.

Index files are written to `logs/` (or the directory pointed to
by `RULE_AUDIT_DIR`) and reused across requests. If the directory
is empty, the indexer builds from `data/kpis.csv` on first call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import load_settings
from app.services.csv_loader import load_kpi_catalog


def build_bm25_index(catalog_csv: Path, out_path: Path) -> dict[str, Any]:
    """Build a BM25 index over the KPI catalog.

    TODO: implement using `rank_bm25` (pure-Python) and persist the
    index to `load_settings().audit_dir`. For now returns a stub
    dict so the surface is stable.
    """

    settings = load_settings()
    catalog = load_kpi_catalog(catalog_csv)
    return {
        "backend": "bm25",
        "size": len(catalog),
        "weights": {"bm25": settings.bm25_weight, "embedding": settings.embedding_weight},
        "path": str(out_path),
    }


def build_embedding_matrix(catalog_csv: Path, out_path: Path) -> dict[str, Any]:
    """Build the semantic embedding matrix.

    TODO: implement char-ngram by default and sentence-transformers
    when `EMBEDDING_BACKEND=sentence-transformers`. Returns a stub.
    """

    settings = load_settings()
    return {
        "backend": settings.embedding_backend,
        "size": 0,
        "path": str(out_path),
    }
