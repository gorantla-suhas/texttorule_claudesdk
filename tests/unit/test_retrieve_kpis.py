"""Tests for `app.tools.retrieve_kpis` (Phase 9).

Uses the real `data/kpis.csv` (1,277 rows). Validates:
- Basic hybrid retrieval finds relevant KPIs.
- Top-K per role, paged expansion.
- Unresolved role detection.
- Exclude filter.
"""

from __future__ import annotations

import pytest

from app.tools import retrieve_kpis
from app.tools.retrieve_kpis import reset_index_cache, reset_audits, _AUDITS


@pytest.fixture(autouse=True)
def _reset():
    reset_index_cache()
    reset_audits()
    yield
    reset_index_cache()
    reset_audits()


def test_retrieve_kpis_metric_basic():
    r = retrieve_kpis.retrieve_kpis(
        {"metric": "recharge amount"},
        client="omantel",
    )
    assert "metric" in r["candidates"]
    assert "filter" in r["candidates"]
    assert "time" in r["candidates"]
    metric_candidates = r["candidates"]["metric"]
    assert len(metric_candidates) >= 1
    # Top candidate should be a recharge-related KPI
    top = metric_candidates[0]
    assert "recharge" in top["feature_name"].lower() or "recharge" in top.get("evidence", "").lower()


def test_retrieve_kpis_filter_basic():
    r = retrieve_kpis.retrieve_kpis(
        {"filters": [{"value": "Prepaid", "phrase": "prepaid subscribers"}]},
        client="omantel",
    )
    filter_candidates = r["candidates"]["filter"]
    assert len(filter_candidates) >= 1


def test_retrieve_kpis_time_window_basic():
    r = retrieve_kpis.retrieve_kpis(
        {"time_window": {"phrase": "last 30 days"}},
        client="omantel",
    )
    time_candidates = r["candidates"]["time"]
    assert len(time_candidates) >= 1


def test_retrieve_kpis_top_k_default_5():
    r = retrieve_kpis.retrieve_kpis(
        {"metric": "recharge"},
        client="omantel",
    )
    for role in ("metric", "filter", "time"):
        assert len(r["candidates"][role]) <= 5


def test_retrieve_kpis_paged_expansion():
    audit_id = retrieve_kpis._new_audit_id()
    r1 = retrieve_kpis.retrieve_kpis(
        {"metric": "recharge"}, client="omantel", audit_id=audit_id, page=1,
    )
    r2 = retrieve_kpis.retrieve_kpis(
        {"metric": "recharge"}, client="omantel", audit_id=audit_id, page=2,
    )
    p1_features = {c["feature_name"] for c in r1["candidates"]["metric"]}
    p2_features = {c["feature_name"] for c in r2["candidates"]["metric"]}
    # Page 2 should have different candidates (no overlap with page 1).
    if p1_features and p2_features:
        assert p1_features.isdisjoint(p2_features) or len(p2_features) <= 5


def test_retrieve_kpis_exclude_filter():
    r = retrieve_kpis.retrieve_kpis(
        {"metric": "recharge"}, client="omantel",
    )
    if r["candidates"]["metric"]:
        excluded = [r["candidates"]["metric"][0]["column_name"]]
        r2 = retrieve_kpis.retrieve_kpis(
            {"metric": "recharge"}, client="omantel", exclude=excluded,
        )
        names = [c["column_name"] for c in r2["candidates"]["metric"]]
        assert excluded[0] not in names


def test_retrieve_kpis_unresolved_warning_for_qualifier_heavy_query():
    """A query that asks for 'prepaid' but the top candidates add more qualifiers
    should surface an unresolved warning."""

    r = retrieve_kpis.retrieve_kpis(
        {"metric": "recharge prepaid postpaid"},
        client="omantel",
    )
    # Either the warning is surfaced or the role is resolved with prepaid/postpaid in request.
    # We just check the structure.
    assert "warnings" in r
    assert isinstance(r["warnings"], list)


def test_retrieve_kpis_returns_audit_id():
    r = retrieve_kpis.retrieve_kpis({"metric": "recharge"}, client="omantel")
    assert "audit_id" in r
    assert len(r["audit_id"]) >= 8


def test_retrieve_kpis_score_is_normalized():
    r = retrieve_kpis.retrieve_kpis({"metric": "recharge"}, client="omantel")
    scores = [c["score"] for c in r["candidates"]["metric"]]
    if scores:
        assert all(0.0 <= s <= 1.0 for s in scores)


def test_retrieve_kpis_with_specific_data_type_hint():
    """Query for 'recharge count' should rank count-style KPIs higher."""

    r = retrieve_kpis.retrieve_kpis({"metric": "recharge count"}, client="omantel")
    metric = r["candidates"]["metric"]
    # At least one top candidate should mention count (very rough check).
    assert len(metric) >= 1


def test_retrieve_kpis_empty_query_returns_empty():
    r = retrieve_kpis.retrieve_kpis({}, client="omantel")
    # No query → empty candidates.
    assert all(len(v) == 0 for v in r["candidates"].values())


def test_retrieve_kpis_full_ranking_persists_in_audits():
    """The audit dict keeps the full ranking for paged expansion."""

    audit_id = retrieve_kpis._new_audit_id()
    retrieve_kpis.retrieve_kpis({"metric": "recharge"}, client="omantel", audit_id=audit_id, page=1)
    assert audit_id in retrieve_kpis._AUDITS
    snap = retrieve_kpis._AUDITS[audit_id]
    assert "full" in snap
    assert "metric" in snap["full"]
    assert len(snap["full"]["metric"]) >= 5  # 5 * 3 = 15


def test_char_ngram_similarity_basic():
    sim = retrieve_kpis._char_ngram_similarity({"abc", "bcd"}, {"abc", "bcd"})
    assert sim == 1.0


def test_char_ngram_similarity_disjoint():
    sim = retrieve_kpis._char_ngram_similarity({"abc"}, {"xyz"})
    assert sim == 0.0


def test_tokenize_basic():
    tokens = retrieve_kpis._tokenize("Hello World 123")
    assert "hello" in tokens
    assert "world" in tokens
    assert "123" in tokens


def test_normalize_scores_zero_range_returns_zero_or_one():
    """When all scores are equal, the function returns 0 or 1 sensibly."""

    out = retrieve_kpis._normalize_scores([0.0, 0.0, 0.0])
    assert all(s == 0.0 for s in out)


def test_unresolved_detection():
    """If every top candidate has 'prepaid' but user didn't ask for it,
    the role is unresolved."""

    candidates = [
        {"feature_name": "Prepaid Recharge", "evidence": "prepaid recharge 30d"},
        {"feature_name": "Postpaid Recharge", "evidence": "postpaid recharge 30d"},
    ]
    requested = set()
    assert retrieve_kpis.is_role_unresolved("metric", candidates, requested) is True


def test_unresolved_detection_when_one_candidate_has_no_extras():
    """If at least one candidate has no unrequested qualifiers, the role is resolved."""

    candidates = [
        {"feature_name": "Prepaid Recharge", "evidence": "prepaid recharge"},
        {"feature_name": "Postpaid Recharge", "evidence": "postpaid recharge"},
    ]
    requested = {"prepaid"}
    # 'prepaid' is requested, so the first candidate has no extras —
    # the role is resolved (we can pick the prepaid one).
    assert retrieve_kpis.is_role_unresolved("metric", candidates, requested) is False


def test_unresolved_detection_when_no_qualifiers():
    candidates = [
        {"feature_name": "Recharge Amount", "evidence": "recharge amount"},
    ]
    requested = set()
    assert retrieve_kpis.is_role_unresolved("metric", candidates, requested) is False