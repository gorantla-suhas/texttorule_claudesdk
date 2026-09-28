"""Tests for `app.tools.message.build_user_message`.

The Python fallback walks the final rule JSON and produces a
short, marketer-facing summary. Tests cover the major tree shapes.
"""

from __future__ import annotations

import pytest

from app.tools.message import build_user_message


def _final_json(*, schedule=None, bonus=False):
    """Build a sample final rule JSON for testing."""

    children = [
        {
            "id": "0_0_0", "pid": "0_0",
            "type": "condition",
            "profile": {"id": 1, "name": "ACCOUNT_TYPE"},
            "operator": "=",
            "values": {"value": "Prepaid"},
        },
        {
            "id": "0_0_1", "pid": "0_0",
            "type": "action",
            "action": {"id": 75, "name": "Send Promotion"},
            "field": [...],
            "request": {
                "field": [
                    {"name": "CHANNEL", "value": "SMS"},
                    {"name": "MESSAGE", "value": "Hello! Top up now."},
                ]
            },
        },
    ]

    if bonus:
        children[-1]["bonus"] = {
            "criteria": [
                {
                    "kpiEnglishName": "Recharge",
                    "kpiProfile": "",
                    "transactionDate": "",
                    "aggregation": "RANGE",
                    "bonusThreshold": 1,
                    "noOfTimes": "1",
                    "noOfDays": "15",
                    "value": "6",
                    "maxValue": "10",
                    "childrens": [],
                }
            ],
            "bonusDetails": [
                {
                    "productId": "123",
                    "successMessage": "You've been awarded a 10 GB data pack.",
                    "errorMessage": "The 10 GB data pack could not be applied.",
                }
            ],
        }

    return {"detail": {"rules": {"id": "0", "pid": "#", "childrens": children, "schedule": schedule or {}}}}


def test_build_user_message_simple_rule():
    rule = _final_json()
    msg = build_user_message(rule, sentence="test")
    assert "Prepaid" in msg.lower() or "account type" in msg.lower()
    assert "Hello" in msg or "promotional" in msg.lower()


def test_build_user_message_clarification_takes_precedence():
    from types import SimpleNamespace
    state = SimpleNamespace(clarification_question="What do you mean by top-up?")
    msg = build_user_message(None, sentence="test", state=state)
    assert msg == "What do you mean by top-up?"


def test_build_user_message_with_bonus():
    rule = _final_json(bonus=True)
    msg = build_user_message(rule, sentence="test")
    assert "between" in msg.lower()
    assert "6" in msg and "10" in msg


def test_build_user_message_with_schedule_interval():
    schedule = {
        "field": [
            {"name": "ScheduleType", "value": "Interval"},
            {"name": "Days", "value": "0"},
            {"name": "Hours", "value": "4"},
            {"name": "Minutes", "value": "0"},
            {"name": "StartDate", "value": "10/02/2025"},
            {"name": "ExpiryDate", "value": "10/03/2026"},
        ]
    }
    rule = _final_json(schedule=schedule)
    msg = build_user_message(rule, sentence="test")
    assert "10/02/2025" in msg
    assert "10/03/2026" in msg


def test_build_user_message_with_schedule_now():
    schedule = {"field": [{"name": "ScheduleType", "value": "ScheduleNow"}]}
    rule = _final_json(schedule=schedule)
    msg = build_user_message(rule, sentence="test")
    assert "immediately" in msg.lower()


def test_build_user_message_with_schedule_daily():
    schedule = {"field": [{"name": "ScheduleType", "value": "Daily"}, {"name": "Time", "value": "10:00"}]}
    rule = _final_json(schedule=schedule)
    msg = build_user_message(rule, sentence="test")
    assert "daily" in msg.lower()


def test_build_user_message_with_warnings():
    rule = _final_json()
    msg = build_user_message(rule, sentence="test", warnings=["Schedule inferred from condition"])
    assert "Notes:" in msg or "Schedule inferred" in msg


def test_build_user_message_no_rule_uses_generic():
    msg = build_user_message(None, sentence="test")
    assert "rephrase" in msg.lower() or "build" in msg.lower()


def test_build_user_message_empty_rule_dict():
    msg = build_user_message({}, sentence="test")
    # Either rephrase prompt or generic message — both acceptable
    assert msg


def test_build_user_message_does_not_leak_internal_names():
    """No KPI catalog column names, profile IDs, action IDs, etc."""

    rule = _final_json()
    msg = build_user_message(rule, sentence="test")
    # IDs like "75" (action_id), "0_0_0" (node ID), "PREPAID" should be absent.
    assert "0_0_0" not in msg
    assert "= 75" not in msg
    assert "pid" not in msg.lower()


def test_build_user_message_with_multiple_conditions():
    rule = {
        "detail": {
            "rules": {
                "id": "0", "pid": "#",
                "childrens": [
                    {
                        "id": "0_0", "pid": "0", "type": "conditions", "option": "All",
                        "childrens": [
                            {
                                "id": "0_0_0", "pid": "0_0",
                                "type": "condition",
                                "profile": {"id": 1, "name": "ACCOUNT_TYPE"},
                                "operator": "=", "values": {"value": "Prepaid"},
                            },
                            {
                                "id": "0_0_1", "pid": "0_0",
                                "type": "condition",
                                "profile": {"id": 2, "name": "RECHARGE_AMOUNT"},
                                "operator": ">", "values": {"value": 50},
                            },
                        ],
                    }
                ],
            }
        }
    }
    msg = build_user_message(rule, sentence="test")
    assert "Prepaid" in msg or "account type" in msg.lower()
    assert "50" in msg or "recharge" in msg.lower()


def test_build_user_message_between_condition():
    rule = {
        "detail": {"rules": {"id": "0", "pid": "#", "childrens": [
            {"id": "0_0", "pid": "0", "type": "conditions", "option": "All",
             "childrens": [
                 {"id": "0_0_0", "pid": "0_0", "type": "condition",
                  "profile": {"id": 1, "name": "RECHARGE_AMOUNT"},
                  "operator": "between", "values": {"fromValue": 6, "toValue": 10}},
             ]}
        ]}}
    }
    msg = build_user_message(rule, sentence="test")
    assert "between" in msg.lower()