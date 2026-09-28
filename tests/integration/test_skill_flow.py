"""Integration test: state + audit + render pipeline (no SDK)."""

import json

from app.schemas import RuleState
from app.tools.record_resolution import record_resolution
from app.tools.render import render_rule
from app.tools.validate import validate_rule
from app.tools.message import build_user_message


def test_full_pipeline_no_llm():
    state = RuleState(
        request_id="test-1", client="omantel",
        sentence="give 5gb data to prepaid users with recharge > 50"
    )

    record_resolution(state, step="condition", selected={"kpi": "recharge_amount_30d"})
    record_resolution(state, step="action", selected={"type": "data_bonus"})

    rule = render_rule(
        template="subscriber_type='prepaid' AND recharge_amount_30d ${operator} ${value}",
        variables={"operator": ">", "value": 50},
        filters=[{"column": "subscriber_type", "op": "=", "value": "prepaid"}],
        client="omantel",
    )
    state.rule = rule

    val = validate_rule(rule, table="360_PROFILE")
    assert val["valid"] is True

    msg = build_user_message(rule, sentence=state.sentence)
    assert isinstance(msg, str)

    assert len(state.audit_log) == 2
    assert json.dumps(rule)  # serializable
