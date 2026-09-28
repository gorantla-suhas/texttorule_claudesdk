"""Tests for `app.services.catalog_lookup`.

These are deterministic; no LLM, no DB. They read `configs/*.yaml`
through the cache-cleared loader and verify the typed accessors.
"""

from __future__ import annotations

import pytest

from app.services import catalog_lookup
from app.tools.config_loader import reload_configs


@pytest.fixture(autouse=True)
def _clear_cache():
    reload_configs()


# ---------------------------------------------------------------------------
# Action catalog
# ---------------------------------------------------------------------------


def test_list_actions_returns_all_entries():
    actions = catalog_lookup.list_actions()
    assert len(actions) >= 10
    types = {a["type"] for a in actions}
    assert "send_sms" in types
    assert "data_bonus" in types


def test_find_action_by_type_case_insensitive():
    a = catalog_lookup.find_action_by_type("DATA_BONUS")
    assert a is not None
    assert a["category"] == "benefit"
    assert a["product_family"] == "data"


def test_find_action_by_type_returns_none_for_unknown():
    assert catalog_lookup.find_action_by_type("nonsense_action") is None


def test_search_actions_by_phrase():
    results = catalog_lookup.search_actions_by_phrase("sms")
    types = [r["type"] for r in results]
    assert "send_sms" in types or "sms_bonus" in types


def test_search_actions_by_phrase_short_token_ignored():
    # Tokens shorter than 3 chars are skipped (filters noise like "is", "to")
    results = catalog_lookup.search_actions_by_phrase("is")
    assert results == []


# ---------------------------------------------------------------------------
# Bonus catalog
# ---------------------------------------------------------------------------


def test_list_bonuses_returns_all():
    bonuses = catalog_lookup.list_bonuses()
    assert len(bonuses) >= 4
    types = {b["type"] for b in bonuses}
    assert "data" in types
    assert "loyalty_points" in types


def test_find_bonus_by_type():
    b = catalog_lookup.find_bonus_by_type("data")
    assert b is not None
    assert "compatible_actions" in b
    assert "data_bonus" in b["compatible_actions"]


def test_compatible_actions_for_bonus():
    compat = catalog_lookup.compatible_actions_for_bonus("data")
    assert "data_bonus" in compat


def test_supported_aggregations_uppercased():
    aggs = catalog_lookup.supported_aggregations("data")
    assert all(a == a.upper() for a in aggs)


# ---------------------------------------------------------------------------
# Schedule catalog
# ---------------------------------------------------------------------------


def test_list_schedule_types_returns_all():
    schedules = catalog_lookup.list_schedule_types()
    assert len(schedules) >= 3
    types = {s["type"] for s in schedules}
    assert "recurring" in types
    assert "rolling" in types


def test_find_schedule_type():
    s = catalog_lookup.find_schedule_type("recurring")
    assert s is not None
    assert "daily" in s.get("supported_recurrences", [])


# ---------------------------------------------------------------------------
# Operator catalog
# ---------------------------------------------------------------------------


def test_list_operators_returns_all():
    ops = catalog_lookup.list_operators()
    assert len(ops) >= 8
    op_keys = {o["op"] for o in ops}
    assert "=" in op_keys
    assert "between" in op_keys
    assert "in" in op_keys


def test_find_operator_with_diamond_alias():
    # "<>" is the catalog's "not equals" alias — operator catalog uses "!="
    # but the if-block syntax uses "<>".
    op = catalog_lookup.find_operator("<>")
    assert op is not None
    assert op["label"] == "not_equals"


def test_operator_valid_for_data_type_numeric():
    assert catalog_lookup.operator_valid_for_data_type(">", "numeric") is True
    assert catalog_lookup.operator_valid_for_data_type("between", "numeric") is True


def test_operator_valid_for_data_type_string_like():
    assert catalog_lookup.operator_valid_for_data_type("like", "string") is True
    assert catalog_lookup.operator_valid_for_data_type("like", "numeric") is False


def test_operator_valid_for_data_type_unknown_op_returns_false():
    assert catalog_lookup.operator_valid_for_data_type("??", "numeric") is False


# ---------------------------------------------------------------------------
# Client config
# ---------------------------------------------------------------------------


def test_get_client_config_omantel():
    cfg = catalog_lookup.get_client_config("omantel")
    assert cfg is not None
    assert cfg["default_currency"] == "OMR"
    assert cfg["default_timezone"] == "Asia/Muscat"


def test_get_client_config_unknown_returns_none():
    assert catalog_lookup.get_client_config("unknown_client") is None


# ---------------------------------------------------------------------------
# Policy catalog (read-only)
# ---------------------------------------------------------------------------


def test_list_policies_returns_all():
    policies = catalog_lookup.list_policies()
    assert len(policies) >= 4


def test_list_policies_filtered_by_client():
    airtel_policies = catalog_lookup.list_policies(client="airtel")
    # Every returned policy either has no scope (universal) or includes airtel.
    for p in airtel_policies:
        scope = p.get("client_scope", [])
        assert not scope or "airtel" in scope


def test_list_policies_omantel():
    omantel_policies = catalog_lookup.list_policies(client="omantel")
    for p in omantel_policies:
        scope = p.get("client_scope", [])
        assert not scope or "omantel" in scope


# ---------------------------------------------------------------------------
# Cross-cutting: cache reset between tests
# ---------------------------------------------------------------------------


def test_cache_resets_between_tests_via_autouse_fixture():
    # Smoke: the autouse fixture has cleared the cache; the next test
    # can rely on fresh reads. Assert catalog data is fresh.
    assert len(catalog_lookup.list_actions()) >= 10