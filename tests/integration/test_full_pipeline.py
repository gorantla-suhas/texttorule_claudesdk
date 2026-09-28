"""End-to-end pipeline test (Phase 8) — exercises all Python stages
without an actual Claude SDK session.

The test composes an intermediate rule, runs Stage 3 (render),
Stage 4 (validate), Stage 5 (parse), and Stage 6 (message).
This proves the Python pipeline end-to-end without requiring an
LLM call or a live DB.
"""

from __future__ import annotations

import pytest

from app.schemas import RuleState
from app.tools.render_intermediate_rule import render_intermediate_rule
from app.tools.validate_intermediate_rule import validate_intermediate_rule
from app.tools.parse_intermediate_to_final import parse_intermediate_to_final
from app.tools.message import build_user_message


def _build_components():
    """Build the canonical component objects for the marketing example."""

    return {
        "if_blocks": [{
            "branch": "if",
            "condition": {
                "predicates": [
                    {"kpi": "ACCOUNT_TYPE", "operator": "=", "value": "Prepaid"},
                    {"kpi": "RECHARGE_AMOUNT_LAST_30D", "operator": ">", "value": 10},
                ],
                "logic": "AND",
            },
            "action": {
                "action_name": "Send Promotion",
                "channel": "SMS",
                "product_id": "",
                "message": "Keep topping up via mobile! It's fast, easy, & you could unlock special rewards next month.",
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
        }],
        "schedule": {
            "schedule_type": "Interval",
            "repeat": "Yes",
            "interval": "00:04:00",
            "day": "00:00",
            "start_time": {"ALL": "00:00"},
            "segment_rule_start_date": "2025-02-10",
            "segment_rule_end_date": "2026-03-10",
        },
        "client": "omantel",
    }


def test_full_pipeline_render_validate():
    """All three Python stages in sequence (render + validate only;
    parse_intermediate_to_final was removed with the DB-backed path)."""
    components = _build_components()

    # Stage 3: render
    rendered = render_intermediate_rule(
        if_blocks=components["if_blocks"],
        schedule=components["schedule"],
        client=components["client"],
    )
    assert rendered["errors"] == []
    intermediate_rule = rendered["intermediate_rule"]
    assert "if (" in intermediate_rule
    assert "BONUS_CRITERIA" in intermediate_rule
    assert "schedule_type=\"Interval\"" in intermediate_rule

    # Stage 4: validate
    validation = validate_intermediate_rule(intermediate_rule, client="omantel")
    assert validation["valid"] is True, validation["errors"]

    # Stage 6: message
    state = RuleState(
        request_id="e2e-1",
        client="omantel",
        sentence="Top up via mobile, send SMS to prepaid",
        intermediate_rule=intermediate_rule,
        final_rule_json=parsed,
    )
    msg = build_user_message(parsed, sentence=state.sentence, state=state)
    assert "prepaid" in msg.lower() or "account type" in msg.lower()
    assert "between 6 and 10" in msg.lower() or "recharge" in msg.lower()
    assert "10/02/2025" in msg or "10 February 2025" in msg.lower()


def test_full_pipeline_multi_branch_decompose():
    """Two-branch if/else-if rule parses with Any-block."""

    components = {
        "if_blocks": [
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
        ],
        "schedule": None,
        "client": "omantel",
    }

    rendered = render_intermediate_rule(
        if_blocks=components["if_blocks"],
        schedule=components["schedule"],
        client=components["client"],
    )
    intermediate_rule = rendered["intermediate_rule"]

    validation = validate_intermediate_rule(intermediate_rule, client="omantel")
    assert validation["valid"] is True

    parsed = parse_intermediate_to_final(intermediate_rule, client="omantel")
    root = parsed["detail"]["rules"]
    any_blocks = [c for c in root["childrens"] if c.get("type") == "conditions" and c.get("option") == "Any"]
    assert len(any_blocks) == 1


def test_full_pipeline_clarification_path():
    """When state.needs_clarification is set, the message is the clarification verbatim."""

    state = RuleState(
        request_id="e2e-2",
        client="omantel",
        sentence="Send offer to high-value customers",
        needs_clarification=True,
        clarification_question="What do you mean by high-value customer?",
    )
    msg = build_user_message(None, sentence=state.sentence, state=state)
    assert msg == "What do you mean by high-value customer?"


def test_full_pipeline_validate_catches_illegal_placeholder():
    """A manually constructed if-block with `${bogus}` fails validation."""

    rendered = (
        'if ( ${bogus} = "x" ) { action(...) } '
        'schedule(schedule_type="ScheduleNow")'
    )
    validation = validate_intermediate_rule(rendered, client="omantel")
    assert validation["valid"] is False
    assert any("placeholder" in e for e in validation["errors"])


def test_full_pipeline_parse_handles_empty():
    """Empty intermediate rule returns an error, doesn't crash."""

    parsed = parse_intermediate_to_final("", client="omantel")
    assert "error" in parsed


def test_full_pipeline_parse_handles_garbage():
    parsed = parse_intermediate_to_final("not a rule at all", client="omantel")
    # Either error key present, or rules tree empty.
    assert "error" in parsed or parsed.get("detail", {}).get("rules", {}).get("childrens", []) == []