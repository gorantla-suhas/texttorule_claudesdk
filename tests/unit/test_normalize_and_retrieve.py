"""Normalize and retrieve stub tests."""

from app.tools.normalize import normalize_slots
from app.tools.vector_search import (
    build_retrieval_audit,
    compact_retrieval_page,
)
from app.tools.render import find_placeholders


def test_normalize_slots_envelope():
    out = normalize_slots("give 5gb data to prepaid users", client="omantel")
    assert out["client"] == "omantel"
    assert "slots" in out


def test_build_retrieval_audit_shape():
    audit = build_retrieval_audit(
        slots={"metric": "recharge"}, client="omantel", exclude=[]
    )
    assert audit["client"] == "omantel"
    assert "metric" in audit["candidates"]


def test_compact_retrieval_page():
    audit = build_retrieval_audit(slots={}, client="omantel")
    page = compact_retrieval_page(audit, audit_id="abc")
    assert page["audit_id"] == "abc"
    assert page["page"] == 1


def test_find_placeholders():
    text = "recharge ${operator} ${value} since ${resolve:tomorrow}"
    ph = find_placeholders(text)
    assert "${operator}" in ph
    assert "${value}" in ph
    assert "${resolve:tomorrow}" in ph
