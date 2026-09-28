"""Tests for `app.tools.extract_segment_markers`."""

from __future__ import annotations

from app.tools.extract_segment_markers import (
    extract_segment_markers,
    has_strong_marker,
    count_strong_markers,
)


def test_empty_input_returns_empty_list():
    assert extract_segment_markers("") == []


def test_simple_sentence_has_no_markers():
    m = extract_segment_markers("Give 5GB to prepaid users with recharge > 50")
    assert m == []


def test_otherwise_is_strong_marker():
    m = extract_segment_markers("Send SMS to active users, otherwise send offer to inactive users")
    assert any(x["marker"] == "otherwise" for x in m)
    assert any(x["kind"] == "split" for x in m)


def test_else_if_is_strong_marker():
    m = extract_segment_markers("If balance > 10 send offer A. Else if balance < 5 send offer B.")
    assert any(x["marker"] == "else if" for x in m)


def test_for_inactive_is_strong_marker():
    m = extract_segment_markers("Send SMS to prepaid users, for inactive users send offer")
    assert any("inactive" in x["marker"] for x in m)


def test_markers_are_sorted_by_position():
    text = "Otherwise send offer to inactive. Else if foo then bar."
    m = extract_segment_markers(text)
    positions = [x["position"] for x in m]
    assert positions == sorted(positions)


def test_marker_positions_actually_point_into_the_input():
    text = "Send SMS to active users, otherwise offer bonus to inactive users"
    m = extract_segment_markers(text)
    for mk in m:
        extracted = text[mk["position"]: mk["position"] + len(mk["raw"])]
        # Case-insensitive match (the regex is lowercased)
        assert extracted.lower() == mk["raw"].lower()


def test_has_strong_marker_helper():
    m = extract_segment_markers("Send SMS, otherwise send offer")
    assert has_strong_marker(m) is True

    m2 = extract_segment_markers("Send SMS to prepaid users")
    assert has_strong_marker(m2) is False


def test_count_strong_markers_helper():
    m = extract_segment_markers("Send SMS, otherwise offer A, else if foo then B")
    n = count_strong_markers(m)
    assert n >= 1


def test_weak_marker_alone_does_not_count_as_strong():
    # "and for the other" is a weak marker (conditional)
    m = extract_segment_markers("Send SMS to active users and for the other users nothing")
    # Could be a weak marker, not strong
    assert not has_strong_marker(m)


def test_bonus_clause_is_not_a_split_marker():
    # "and if ... then provide ..." is a bonus trigger, not a split.
    # Our markers should NOT mark this as a split. (Claude reasons
    # about whether it's a bonus vs a branch separately.)
    text = (
        "Send a promotional SMS to prepaid users. "
        "And if the customer recharges between 6 and 10, provide a 10 GB data pack."
    )
    m = extract_segment_markers(text)
    # Should be empty — no otherwise/else/for-other/etc.
    assert m == []