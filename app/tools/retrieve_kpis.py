"""KPI retrieval — hybrid BM25 + char-ngram embedding (Phase 9).

Implements:
- BM25 over the KPI catalog's text fields (feature_name, aliases,
  description, search_text, group_name).
- Char n-gram embedding for semantic similarity (default backend).
- Hybrid score = `0.5 * normalized_bm25 + 0.5 * normalized_embedding`.
- Paged expansion: page 1 returns top-5 per role, page 2 returns
  ranks 6-10, page 3 returns 11-15.
- Expand only when the role is unresolved (every candidate adds
  unrequested business qualifiers).

Pure Python. No external dependencies beyond what's already in
`requirements.txt` (no numpy, no rank_bm25). Fast enough for the
catalog size (~1,277 rows).
"""

from __future__ import annotations

import csv
import math
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    """Return the set of character n-grams (lowercased, whitespace normalized)."""

    t = re.sub(r"\s+", " ", (text or "").lower())
    if len(t) < n:
        return set()
    return {t[i: i + n] for i in range(len(t) - n + 1)}


# ---------------------------------------------------------------------------
# BM25 implementation
# ---------------------------------------------------------------------------


class _BM25:
    """Minimal BM25 Okapi implementation, pure Python."""

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs = docs
        self.doc_lens = [len(d) for d in docs]
        self.avg_dl = (sum(self.doc_lens) / len(docs)) if docs else 0.0
        self.df: dict[str, int] = {}
        for d in docs:
            for term in set(d):
                self.df[term] = self.df.get(term, 0) + 1
        self.n_docs = len(docs)

    def score(self, query: list[str]) -> list[float]:
        out = [0.0] * self.n_docs
        for term in query:
            df = self.df.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))
            for i, d in enumerate(self.docs):
                tf = d.count(term)
                if tf == 0:
                    continue
                dl = self.doc_lens[i]
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avg_dl or 1))
                out[i] += idf * (tf * (self.k1 + 1)) / (denom or 1)
        return out


# ---------------------------------------------------------------------------
# Catalog load + index cache (per process)
# ---------------------------------------------------------------------------


_INDEX_LOCK = threading.Lock()
_INDEX: dict[str, Any] = {
    "bm25": None,
    "char_ngrams": None,
    "rows": None,
}


def _kpi_csv_path() -> Path:
    """Return the path to `data/kpis.csv`. Resolves via app.config."""

    from app.config import DATA_DIR
    return DATA_DIR / "kpis.csv"


def _load_catalog() -> list[dict[str, str]]:
    """Load the KPI catalog from CSV. Cached per process."""

    with _INDEX_LOCK:
        if _INDEX["rows"] is not None:
            return _INDEX["rows"]

        path = _kpi_csv_path()
        rows: list[dict[str, str]] = []
        try:
            with path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(dict(row))
        except FileNotFoundError:
            pass

        _INDEX["rows"] = rows
        _build_indexes(rows)
        return rows


def _build_indexes(rows: list[dict[str, str]]) -> None:
    """Build BM25 and char-ngram indexes from the catalog rows."""

    docs: list[list[str]] = []
    ngrams: list[set[str]] = []

    for row in rows:
        # Concatenate the text fields we want to search over.
        text_parts = [
            row.get("feature_name", ""),
            row.get("aliases", ""),
            row.get("description", ""),
            row.get("search_text", ""),
            row.get("group_name", ""),
        ]
        text = " ".join(text_parts)
        docs.append(_tokenize(text))
        ngrams.append(_char_ngrams(text))

    _INDEX["bm25"] = _BM25(docs)
    _INDEX["char_ngrams"] = ngrams


def reset_index_cache() -> None:
    """Clear the cached catalog index. Used by tests."""

    with _INDEX_LOCK:
        _INDEX["bm25"] = None
        _INDEX["char_ngrams"] = None
        _INDEX["rows"] = None


# ---------------------------------------------------------------------------
# Score a single role against the catalog
# ---------------------------------------------------------------------------


_UNREQUESTED_QUALIFIER_TOKENS = (
    "prepaid", "postpaid",
    "incoming", "outgoing",
    "local", "international", "idd",
    "onnet", "offnet",
    "roaming",
    "bundle", "payg", "free",
    "eid", "ramadan", "hajj", "salalah",  # specialty period hints
    "voice", "data", "sms",  # sub-types if not asked
)


def _has_unrequested_qualifier(text: str, requested: set[str]) -> bool:
    """True if `text` contains a token that looks like a business qualifier
    not in `requested`."""

    tokens = set(_tokenize(text))
    extras = tokens & set(_UNREQUESTED_QUALIFIER_TOKENS)
    # Strip out tokens the user did request.
    extras -= requested
    return bool(extras)


def _normalize_scores(scores: list[float]) -> list[float]:
    """Min-max normalize to [0, 1]. Zeros stay zero."""

    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi <= lo:
        return [1.0 if s > 0 else 0.0 for s in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def _char_ngram_similarity(query_ngrams: set[str], doc_ngrams: set[str]) -> float:
    """Jaccard similarity between two sets of n-grams."""

    if not query_ngrams or not doc_ngrams:
        return 0.0
    intersection = query_ngrams & doc_ngrams
    union = query_ngrams | doc_ngrams
    return len(intersection) / len(union) if union else 0.0


def _score_role(role: str, query_text: str, requested_qualifiers: set[str],
               top_k: int, page: int) -> list[dict[str, Any]]:
    """Score a single role and return the page slice.

    Returns: list of candidate dicts for the requested page.
    Empty query → empty results (don't return arbitrary catalog rows).
    """

    rows = _INDEX["rows"] or []
    bm25: _BM25 = _INDEX["bm25"]
    ngrams: list[set[str]] = _INDEX["char_ngrams"]

    if not rows or bm25 is None or ngrams is None:
        return []

    q_tokens = _tokenize(query_text)
    q_ngrams = _char_ngrams(query_text)

    if not q_tokens and not q_ngrams:
        # Empty query — don't return arbitrary catalog rows.
        return []

    bm25_scores = bm25.score(q_tokens) if q_tokens else [0.0] * len(rows)
    emb_scores = [
        _char_ngram_similarity(q_ngrams, doc_ng) for doc_ng in ngrams
    ]

    bm25_norm = _normalize_scores(bm25_scores)
    emb_norm = _normalize_scores(emb_scores)

    # Hybrid = 0.5 * bm25_norm + 0.5 * embedding_norm.
    hybrid = [0.5 * b + 0.5 * e for b, e in zip(bm25_norm, emb_norm)]

    # Sort by score, take top (5 * page) so page 1 is top-5, page 2 is 6-10, etc.
    total = top_k * page
    ranked = sorted(
        enumerate(hybrid),
        key=lambda x: x[1],
        reverse=True,
    )[:total]

    # Page slice: page 1 → top_k, page 2 → next top_k, etc.
    start = (page - 1) * top_k
    end = start + top_k
    page_slice = ranked[start:end]

    out: list[dict[str, Any]] = []
    for idx, score in page_slice:
        row = rows[idx]
        # Concatenate a short evidence string.
        evidence_parts = [
            f"feature: {row.get('feature_name', '')}",
            f"group: {row.get('group_name', '')}",
        ]
        if row.get("aliases"):
            evidence_parts.append(f"aliases: {row['aliases'][:60]}")
        if row.get("data_type"):
            evidence_parts.append(f"data_type: {row['data_type']}")
        out.append({
            "id": row.get("id", ""),
            "feature_name": row.get("feature_name", ""),
            "group_name": row.get("group_name", ""),
            "data_type": row.get("data_type", ""),
            "kpi_type": row.get("kpi_type", ""),
            "time_window_value": row.get("time_window_value", ""),
            "column_name": row.get("column_name", ""),
            "score": round(score, 4),
            "evidence": "; ".join(evidence_parts),
        })
    return out


def is_role_unresolved(role: str, candidates: list[dict[str, Any]],
                       requested_qualifiers: set[str]) -> bool:
    """True when every candidate in `candidates` adds an unrequested
    business qualifier.

    A role is considered "resolved" if:
      - the role is empty (no candidates returned), OR
      - at least one candidate has no unrequested qualifiers
    """

    if not candidates:
        return False
    for c in candidates:
        haystack = " ".join([
            str(c.get("feature_name", "")),
            str(c.get("group_name", "")),
            str(c.get("evidence", "")),
        ])
        if not _has_unrequested_qualifier(haystack, requested_qualifiers):
            return False
    return True


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


# Per-request audit dicts. Targeted expansion reuses the original
# ranking without putting it in model context.
_AUDITS: dict[str, dict[str, Any]] = {}
_AUDIT_LOCK = threading.Lock()


def _audit_id() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def _tokenize_role_request(slots: dict[str, Any], role: str) -> str:
    """Build the query text for a role from the slots."""

    if role == "metric":
        m = slots.get("metric")
        if isinstance(m, dict):
            return m.get("phrase") or m.get("value") or ""
        return str(m or "")
    if role == "filter":
        filters = slots.get("filters", []) or []
        return " ".join(
            f.get("phrase") or str(f.get("value", ""))
            for f in filters if isinstance(f, dict)
        )
    if role == "time":
        tw = slots.get("time_window")
        if isinstance(tw, dict):
            return tw.get("phrase") or ""
        return str(tw or "")
    return ""


def _requested_qualifiers(slots: dict[str, Any]) -> set[str]:
    """Pull user-specified qualifier tokens from the slots."""

    out: set[str] = set()
    filters = slots.get("filters", []) or []
    for f in filters:
        if isinstance(f, dict):
            v = f.get("value")
            if isinstance(v, str):
                out.update(_tokenize(v))
            if "phrase" in f:
                out.update(_tokenize(f["phrase"]))
    metric = slots.get("metric")
    if isinstance(metric, dict):
        v = metric.get("value") or metric.get("phrase")
        if isinstance(v, str):
            out.update(_tokenize(v))
    elif isinstance(metric, str):
        out.update(_tokenize(metric))
    return out


def retrieve_kpis(
    slots: dict[str, Any],
    *,
    client: str = "omantel",
    exclude: list[str] | None = None,
    audit_id: str | None = None,
    expand_roles: list[str] | None = None,
    page: int = 1,
    top_k: int = 5,
    min_score: float = 0.25,
) -> dict[str, Any]:
    """Hybrid BM25 + char-ngram KPI retrieval.

    Returns:

        {
          "audit_id": str,
          "page": int,
          "candidates": {
            "metric": [ {feature_name, ...}, ... ],
            "filter": [ ... ],
            "time":   [ ... ],
          },
          "warnings": [ ... ]
        }
    """

    exclude = exclude or []
    expand_roles = expand_roles or []
    min_score = float(min_score)

    # Build or fetch audit snapshot.
    with _AUDIT_LOCK:
        if audit_id and audit_id in _AUDITS:
            snap = _AUDITS[audit_id]
            # If the snap is uninitialized (e.g. from _new_audit_id),
            # populate it now.
            if not snap.get("full") and not snap.get("slots"):
                snap["slots"] = dict(slots)
                snap["client"] = client
                _populate_snap_full(snap, slots)
        else:
            # First call: build the full ranking for every role.
            _load_catalog()  # populates _INDEX
            new_id = audit_id or _audit_id()
            snap = {"slots": dict(slots), "client": client, "full": {}, "unresolved": {}}
            _populate_snap_full(snap, slots)
            _AUDITS[new_id] = snap

    # Build the page slice per role.
    candidates: dict[str, list[dict[str, Any]]] = {}
    warnings: list[str] = []

    for role in ("metric", "filter", "time"):
        full = snap["full"].get(role, [])
        # Exclude roles the caller asked to skip.
        if role in expand_roles:
            # Caller wants page 2 or 3 for this role.
            start = (page - 1) * top_k
            end = start + top_k
            slice_ = full[start:end]
            warnings.append(f"expanded {role} to page {page}")
        else:
            slice_ = full[:top_k]

        # Apply exclude filter.
        slice_ = [c for c in slice_ if c.get("column_name", "") not in exclude
                  and c.get("feature_name", "") not in exclude]

        # Quality gate: drop candidates below the score threshold. The
        # model should never see weak matches -- only good matches or
        # empty results. This stops the model from improvising KPIs
        # out of low-relevance candidates.
        before_score = len(slice_)
        slice_ = [c for c in slice_ if float(c.get("score", 0.0)) >= min_score]
        if before_score and not slice_:
            warnings.append(
                f"{role} role: no candidate meets min_score={min_score}; "
                "broaden the query or call retrieve_kpis again with "
                "expand_roles=['" + role + "'] and page=2"
            )

        # Mark unresolved so the caller can decide whether to expand.
        is_unresolved = snap["unresolved"].get(role, False) and not expand_roles
        if is_unresolved:
            warnings.append(
                f"{role} role appears unresolved (every top candidate adds "
                "an unrequested business qualifier); call retrieve_kpis "
                "with expand_roles=['" + role + "'] and page=2"
            )

        candidates[role] = slice_

    return {
        "audit_id": audit_id or _new_audit_id(),
        "page": page,
        "candidates": candidates,
        "warnings": warnings,
    }


def _new_audit_id() -> str:
    """Public API to get a new audit id (mostly for tests)."""

    new_id = _audit_id()
    # Pre-populate so the next call with this id finds it.
    with _AUDIT_LOCK:
        if new_id not in _AUDITS:
            _AUDITS[new_id] = {"slots": {}, "client": "omantel", "full": {}, "unresolved": {}}
    return new_id


def _populate_snap_full(snap: dict[str, Any], slots: dict[str, Any]) -> None:
    """Fill `snap['full']` with the complete ranking for every role.

    Builds top-K * 3 so page 1 (top 5), page 2 (6-10), and
    page 3 (11-15) are all available without re-running retrieval.
    """

    _load_catalog()
    requested_quals = _requested_qualifiers(slots)
    for role in ("metric", "filter", "time"):
        qtext = _tokenize_role_request(slots, role)
        snap["full"][role] = _score_role(role, qtext, requested_quals, top_k=5, page=3)
        snap["unresolved"][role] = is_role_unresolved(
            role, snap["full"][role][:5], requested_quals,
        )


def reset_audits() -> None:
    """Clear all stored audits (tests)."""

    with _AUDIT_LOCK:
        _AUDITS.clear()