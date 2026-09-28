"""Hybrid KPI retrieval over the canonical KPI catalog.

Combines BM25 over structured fields with a character n-gram
embedding scorer (or, if `EMBEDDING_BACKEND=sentence-transformers`, a
real embedding model). Returns up to `top_k` candidates per role
(metric, filter, time) with score components and concise evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import load_settings


@dataclass(frozen=True)
class Candidate:
    """Single KPI candidate returned by the retriever."""

    id: str
    feature_name: str
    group_name: str
    description: str
    data_type: str
    time_window_value: str
    score: float
    reason: str
    bm25_score: float = 0.0
    semantic_score: float = 0.0
    bm25_norm: float = 0.0
    embedding_norm: float = 0.0
    hybrid_score: float = 0.0
    metadata_boost: float = 0.0
    client_prior: float = 0.0


def build_retrieval_audit(
    slots: dict[str, Any],
    client: str,
    exclude: list[str] | None = None,
) -> dict[str, Any]:
    """Build the full retrieval audit for a request.

    TODO: implement BM25 + char-ngram hybrid scoring, candidate
    ranking, metadata boosts, and client priors. This stub returns
    an empty audit envelope so the import surface is stable.
    """

    settings = load_settings()
    return {
        "client": client,
        "slots": slots,
        "exclude": exclude or [],
        "settings": {
            "embedding_backend": settings.embedding_backend,
            "retrieval_top_k": settings.retrieval_top_k,
            "bm25_weight": settings.bm25_weight,
            "embedding_weight": settings.embedding_weight,
        },
        "candidates": {"metric": [], "filter": [], "time": []},
    }


def compact_retrieval_page(
    audit: dict[str, Any],
    *,
    audit_id: str,
    role_ids: list[str] | None = None,
    page: int = 1,
) -> dict[str, Any]:
    """Return the compact per-role view of the audit that the agent sees.

    The full audit stays in the per-request store; only the compact
    view crosses into model context.
    """

    return {
        "audit_id": audit_id,
        "page": page,
        "roles": role_ids or ["metric", "filter", "time"],
        "candidates": audit.get("candidates", {}),
    }


def serialize_retrieval_audit(audit: dict[str, Any]) -> str:
    """Stringify the full audit for Langfuse / log persistence."""

    return json.dumps(audit, default=str, sort_keys=True)
