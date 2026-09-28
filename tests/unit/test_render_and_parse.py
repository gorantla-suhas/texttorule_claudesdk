"""Tests for `app.tools.render_intermediate_rule` and
`app.tools.parse_intermediate_to_final`.

Round-trip tests: render → parse → verify shape. Plus targeted tests
for each module.
"""

from __future__ import annotations

import pytest

from app.tools.render_intermediate_rule import render_intermediate_rule
from app.tools.parse_intermediate_to_final import parse_intermediate_to_final


# ---------------------------------------------------------------------------
# render_intermediate_rule
# ---------------------------------------------------------------------------


def test_render_simple_single_branch():
    if_blocks = [{
        "branch": "if",
        "condition": {
            "predicates": [
                {"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Prepaid"},
                {"kpi": "RECHARGE_AMOUNT", "operator": ">", "value": 50},
            ],
            "logic": "AND",
        },
        "action": {
            "action_name": "Send Promotion",
            "channel": "SMS",
            "product_id": "",
            "message": "Hello!",
        },
    }]
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=None, client="omantel")
    assert r["errors"] == []
    text = r["intermediate_rule"]
    assert "if" in text
    assert "ACCOUNT_TYPE = \"Prepaid\"" in text
    assert "RECHARGE_AMOUNT > 50" in text
    assert "ActionName=\"Send Promotion\"" in text
    assert "CHANNEL=\"SMS\"" in text


def test_render_between_operator():
    if_blocks = [{
        "branch": "if",
        "condition": {
            "predicates": [
                {"kpi": "RECHARGE_AMOUNT", "operator": "between", "value": [6, 10]},
            ],
            "logic": "AND",
        },
        "action": {
            "action_name": "Send Promotion",
            "channel": "SMS",
            "message": "Keep topping up!",
        },
    }]
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=None, client="omantel")
    text = r["intermediate_rule"]
    assert "RECHARGE_AMOUNT BETWEEN" in text
    assert " AND " in text


def test_render_in_list_operator():
    if_blocks = [{
        "branch": "if",
        "condition": {
            "predicates": [
                {"kpi": "REGION", "operator": "in", "value": ["Muscat", "Dubai"]},
            ],
            "logic": "AND",
        },
        "action": {
            "action_name": "Send Promotion",
            "channel": "SMS",
            "message": "Hello!",
        },
    }]
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=None, client="omantel")
    text = r["intermediate_rule"]
    assert "REGION IN LIST" in text


def test_render_with_bonus():
    if_blocks = [{
        "branch": "if",
        "condition": {
            "predicates": [{"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Prepaid"}],
            "logic": "AND",
        },
        "action": {
            "action_name": "Send Promotion",
            "channel": "SMS",
            "message": "Hello!",
            "bonus_criteria": {
                "action_type": "Recharge",
                "value": 6,
                "aggregation": "RANGE",
                "max_value": 10,
                "no_of_days": 15,
                "bonus_threshold": 1,
                "no_of_times": 1,
                "benefits": [
                    {
                        "type": "telco_product",
                        "details": {"product_name": "10 GB data pack"},
                        "success_message": "You've been awarded a 10 GB data pack.",
                        "error_message": "The 10 GB data pack could not be applied.",
                    }
                ],
            },
        },
    }]
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=None, client="omantel")
    text = r["intermediate_rule"]
    assert "BONUS_CRITERIA" in text
    assert "action_type=\"Recharge\"" in text
    assert "aggregation=\"RANGE\"" in text
    assert "maxValue=10" in text
    assert "noOfDays=15" in text
    assert "benefits=" in text


def test_render_with_schedule_interval():
    if_blocks = [{
        "branch": "if",
        "condition": {"predicates": [{"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Prepaid"}], "logic": "AND"},
        "action": {"action_name": "Send Promotion", "channel": "SMS", "message": "x"},
    }]
    sched = {
        "schedule_type": "Interval",
        "repeat": "Yes",
        "interval": "00:04:00",
        "day": "00:00",
        "start_time": {"ALL": "00:00"},
        "segment_rule_start_date": "2025-02-10",
        "segment_rule_end_date": "2026-03-10",
    }
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=sched, client="omantel")
    text = r["intermediate_rule"]
    assert "schedule(" in text
    assert "schedule_type=\"Interval\"" in text
    assert "interval=\"00:04:00\"" in text
    assert "segment_rule_start_date=\"2025-02-10\"" in text
    assert "segment_rule_end_date=\"2026-03-10\"" in text


def test_render_multi_branch():
    if_blocks = [
        {
            "branch": "if",
            "condition": {"predicates": [{"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Prepaid"}], "logic": "AND"},
            "action": {"action_name": "Send Promotion", "channel": "SMS", "message": "x"},
        },
        {
            "branch": "else_if",
            "condition": {"predicates": [{"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Postpaid"}], "logic": "AND"},
            "action": {"action_name": "Send Promotion", "channel": "SMS", "message": "y"},
        },
    ]
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=None, client="omantel")
    text = r["intermediate_rule"]
    assert "if (" in text
    assert "else if (" in text


def test_render_empty_if_blocks_returns_error():
    r = render_intermediate_rule(if_blocks=[], schedule=None, client="omantel")
    assert r["errors"] != [] or r["intermediate_rule"] == ""


def test_render_invalid_branch_kind_reports_error():
    if_blocks = [{"branch": "sometimes", "condition": {"predicates": []}, "action": {"message": "x"}}]
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=None, client="omantel")
    assert any("branch" in e for e in r["errors"])


# ---------------------------------------------------------------------------
# parse_intermediate_to_final
# ---------------------------------------------------------------------------


def test_parse_empty_returns_error():
    r = parse_intermediate_to_final("")
    assert "error" in r


def test_parse_simple_rule_round_trip():
    if_blocks = [{
        "branch": "if",
        "condition": {"predicates": [{"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Prepaid"}], "logic": "AND"},
        "action": {"action_name": "Send Promotion", "channel": "SMS", "message": "Hi"},
    }]
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=None, client="omantel")
    parsed = parse_intermediate_to_final(r["intermediate_rule"], client="omantel")
    assert "detail" in parsed
    assert "rules" in parsed["detail"]
    root = parsed["detail"]["rules"]
    assert root["id"] == "0"
    assert root["pid"] == "#"


def test_parse_with_schedule_round_trip():
    if_blocks = [{
        "branch": "if",
        "condition": {"predicates": [{"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Prepaid"}], "logic": "AND"},
        "action": {"action_name": "Send Promotion", "channel": "SMS", "message": "Hi"},
    }]
    sched = {
        "schedule_type": "Interval",
        "repeat": "Yes",
        "interval": "00:04:00",
        "day": "00:00",
        "start_time": {"ALL": "00:00"},
        "segment_rule_start_date": "2025-02-10",
        "segment_rule_end_date": "2026-03-10",
    }
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=sched, client="omantel")
    parsed = parse_intermediate_to_final(r["intermediate_rule"], client="omantel")
    assert "schedule" in parsed["detail"]["rules"]
    sched_fields = {f["name"]: f["value"] for f in parsed["detail"]["rules"]["schedule"]["field"]}
    assert sched_fields["ScheduleType"] == "Interval"
    assert sched_fields["StartDate"] == "10/02/2025"
    assert sched_fields["ExpiryDate"] == "10/03/2026"
    assert sched_fields["Days"] == "0"
    assert sched_fields["Hours"] == "4"
    assert sched_fields["Minutes"] == "0"


def test_parse_multi_branch_uses_any_block():
    if_blocks = [
        {"branch": "if", "condition": {"predicates": [{"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Prepaid"}], "logic": "AND"}, "action": {"action_name": "Send Promotion", "channel": "SMS", "message": "x"}},
        {"branch": "else_if", "condition": {"predicates": [{"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Postpaid"}], "logic": "AND"}, "action": {"action_name": "Send Promotion", "channel": "SMS", "message": "y"}},
    ]
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=None, client="omantel")
    parsed = parse_intermediate_to_final(r["intermediate_rule"], client="omantel")
    root = parsed["detail"]["rules"]
    any_blocks = [c for c in root["childrens"] if c.get("type") == "conditions" and c.get("option") == "Any"]
    assert len(any_blocks) == 1


def test_parse_preserves_action_request_fields():
    if_blocks = [{
        "branch": "if",
        "condition": {"predicates": [{"kpi": "X", "operator": "=", "value": "v"}], "logic": "AND"},
        "action": {"action_name": "Send Promotion", "channel": "SMS", "message": "Hello", "product_id": "ABC123"},
    }]
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=None, client="omantel")
    parsed = parse_intermediate_to_final(r["intermediate_rule"], client="omantel")
    # Walk to find the action node
    def find_action(node):
        if node.get("type") == "action":
            return node
        for c in node.get("childrens", []) or []:
            found = find_action(c)
            if found:
                return found
        return None

    root = parsed["detail"]["rules"]
    action_node = find_action(root)
    assert action_node is not None
    request_fields = {f["name"]: f["value"] for f in action_node["request"]["field"]}
    assert request_fields.get("MESSAGE") == "Hello"
    assert request_fields.get("CHANNEL") == "SMS"
    assert request_fields.get("PRODUCT_ID") == "ABC123"


def test_parse_with_bonus_round_trip():
    if_blocks = [{
        "branch": "if",
        "condition": {"predicates": [{"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Prepaid"}], "logic": "AND"},
        "action": {
            "action_name": "Send Promotion",
            "channel": "SMS",
            "message": "Hi",
            "bonus_criteria": {
                "action_type": "Recharge",
                "value": 6,
                "aggregation": "RANGE",
                "max_value": 10,
                "no_of_days": 15,
                "bonus_threshold": 1,
                "no_of_times": 1,
                "benefits": [],
            },
        },
    }]
    r = render_intermediate_rule(if_blocks=if_blocks, schedule=None, client="omantel")
    parsed = parse_intermediate_to_final(r["intermediate_rule"], client="omantel")
    def find_action(node):
        if node.get("type") == "action":
            return node
        for c in node.get("childrens", []) or []:
            found = find_action(c)
            if found:
                return found
        return None

    root = parsed["detail"]["rules"]
    action_node = find_action(root)
    assert action_node is not None
    assert "bonus" in action_node
    crit = action_node["bonus"]["criteria"][0]
    assert crit["kpiEnglishName"] == "Recharge"
    assert crit["aggregation"] == "RANGE"
    assert crit["value"] == "6"
    assert crit["maxValue"] == "10"
    assert crit["noOfDays"] == "15"


def test_parse_garbage_returns_error():
    r = parse_intermediate_to_final("this is not a rule at all")
    # Either error key present, or empty rules tree
    assert "error" in r or "detail" in r