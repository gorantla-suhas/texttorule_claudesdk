"""Tests for the Stage 2 lookup tools.

All deterministic, no LLM, no DB.
"""

from __future__ import annotations

import pytest

from app.tools import lookup_action, lookup_bonus, lookup_schedule, lookup_policy
from app.tools.lookup_schedule import validate_schedule_dict, SCHEDULE_TYPES
from app.tools.config_loader import reload_configs


@pytest.fixture(autouse=True)
def _clear_cache():
    reload_configs()


# ---------------------------------------------------------------------------
# lookup_action
# ---------------------------------------------------------------------------


def test_lookup_action_finds_send_sms():
    r = lookup_action.lookup_action("send sms", client="omantel")
    assert r["match_count"] >= 1
    types = [a["type"] for a in r["actions"]]
    assert "send_sms" in types


def test_lookup_action_finds_data_bonus():
    r = lookup_action.lookup_action("data bonus", client="omantel")
    types = [a["type"] for a in r["actions"]]
    assert "data_bonus" in types


def test_lookup_action_empty_phrase():
    r = lookup_action.lookup_action("", client="omantel")
    assert r["match_count"] == 0
    assert r["actions"] == []


def test_lookup_action_returns_required_params():
    r = lookup_action.lookup_action("send sms", client="omantel")
    send_sms = next(a for a in r["actions"] if a["type"] == "send_sms")
    assert "template_id" in send_sms["required_params"]


def test_get_required_params_helper():
    params = lookup_action.get_required_params("send_sms")
    assert "template_id" in params


def test_get_default_params_helper():
    defaults = lookup_action.get_default_params("data_bonus")
    assert defaults.get("validity_days") == 30


# ---------------------------------------------------------------------------
# lookup_bonus
# ---------------------------------------------------------------------------


def test_lookup_bonus_with_data_bonus_type():
    # The bonus catalog's type is "data" (not "Recharge" — that's the
    # user-facing action_type field on BonusCriteria). This round:
    # only "Recharge" action_type is emitted, but it pairs with the
    # "data" catalog entry.
    r = lookup_bonus.lookup_bonus("data", "SUM", client="omantel")
    assert r["bonus_template"].get("type") == "data"
    assert isinstance(r["warnings"], list)


def test_lookup_bonus_unknown_action_type_warns():
    r = lookup_bonus.lookup_bonus("UnknownType", "SUM", client="omantel")
    assert r["bonus_template"] == {}
    assert any("not in the bonus catalog" in w for w in r["warnings"])


def test_lookup_bonus_no_product_query_returns_empty_benefits():
    r = lookup_bonus.lookup_bonus("data", "SUM", client="omantel", product_query=None)
    assert r["benefits"] == []


def test_lookup_bonus_with_product_query_calls_sql():
    # DB is not configured, so get_product_by_name_or_id returns None
    r = lookup_bonus.lookup_bonus("data", "SUM", client="omantel", product_query="10 GB data pack")
    assert len(r["benefits"]) == 1
    assert r["benefits"][0]["type"] == "telco_product"
    assert r["benefits"][0]["product_name"] == "10 GB data pack"
    assert r["benefits"][0]["product_id"] is None   # DB stub returns None
    assert r["benefits"][0]["resolved"] is False


def test_lookup_bonus_aggregation_warning():
    # Outside SUM/COUNT/RANGE this round → warning
    r = lookup_bonus.lookup_bonus("data", "PER_SUBSCRIBER", client="omantel", product_query=None)
    assert any("SUM/COUNT/RANGE" in w for w in r["warnings"])


# ---------------------------------------------------------------------------
# lookup_schedule
# ---------------------------------------------------------------------------


def test_lookup_schedule_returns_valid_types():
    r = lookup_schedule.lookup_schedule("every Monday at 9am", client="omantel")
    assert "Weekly" in r["valid_types"]
    assert len(r["valid_types"]) == 9


def test_lookup_schedule_empty_phrase_still_returns_types():
    r = lookup_schedule.lookup_schedule("", client="omantel")
    assert len(r["valid_types"]) == 9


def test_validate_schedule_dict_daily():
    sched = {
        "schedule_type": "Daily",
        "repeat": "Yes",
        "day": "10:00",
        "start_time": {"ALL": "10:00"},
    }
    r = validate_schedule_dict(sched)
    assert r["valid"] is True
    assert r["errors"] == []


def test_validate_schedule_dict_weekly_requires_select_days():
    sched = {
        "schedule_type": "Weekly",
        "repeat": "Yes",
        "day": "MON 09:00",
    }
    r = validate_schedule_dict(sched)
    assert r["valid"] is False
    assert any("select_days" in e for e in r["errors"])


def test_validate_schedule_dict_interval_format():
    sched = {
        "schedule_type": "Interval",
        "repeat": "Yes",
        "interval": "00:04:00",
        "day": "00:00",
        "start_time": {"ALL": "00:00"},
    }
    r = validate_schedule_dict(sched)
    assert r["valid"] is True


def test_validate_schedule_dict_rejects_bad_interval_format():
    sched = {
        "schedule_type": "Interval",
        "repeat": "Yes",
        "interval": "4:00",       # not DD:HH:MM
        "day": "00:00",
    }
    r = validate_schedule_dict(sched)
    assert r["valid"] is False
    assert any("DD:HH:MM" in e for e in r["errors"])


def test_validate_schedule_dict_rejects_bad_date_format():
    sched = {
        "schedule_type": "Interval",
        "repeat": "Yes",
        "interval": "00:04:00",
        "day": "00:00",
        "segment_rule_start_date": "10 February 2025",   # not ISO
    }
    r = validate_schedule_dict(sched)
    assert r["valid"] is False


def test_validate_schedule_dict_unknown_type():
    sched = {"schedule_type": "EveryTuesday"}
    r = validate_schedule_dict(sched)
    assert r["valid"] is False
    assert any("ScheduleNow" in e for e in r["errors"])  # error message lists all 9 types


def test_validate_schedule_dict_not_a_dict():
    r = validate_schedule_dict("not a dict")  # type: ignore[arg-type]
    assert r["valid"] is False


def test_validate_schedule_dict_missing_type():
    r = validate_schedule_dict({})
    assert r["valid"] is False


# ---------------------------------------------------------------------------
# lookup_policy
# ---------------------------------------------------------------------------


def test_lookup_policy_returns_empty_deferred():
    r = lookup_policy.lookup_policy("omantel", audience={}, bonus_type="data")
    assert r["conflicts"] == []
    assert r["eligibility"] == {}
    assert r["exclusions"] == []
    assert any("deferred" in w for w in r["warnings"])


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------


def test_all_nine_schedule_types_documented():
    assert len(SCHEDULE_TYPES) == 9
    assert "ScheduleNow" in SCHEDULE_TYPES
    assert "Interval" in SCHEDULE_TYPES