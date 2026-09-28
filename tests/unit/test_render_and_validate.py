"""Render and validate stub tests."""

from app.tools.render import render_rule, find_placeholders
from app.tools.validate import validate_rule


def test_render_rule_envelope():
    rule = render_rule(
        template="x ${operator} ${value}",
        variables={"operator": ">", "value": 50},
        filters=[],
        client="omantel",
    )
    assert rule["client"] == "omantel"
    assert rule["template"] == "x ${operator} ${value}"


def test_find_placeholders_unique():
    ph = find_placeholders("a ${operator} b ${operator} c")
    assert ph == {"${operator}"}


def test_validate_rule_stub():
    out = validate_rule({"parent_condition": "x ${operator} ${value}"})
    assert out["valid"] is True
