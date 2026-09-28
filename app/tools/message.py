"""User-facing message builder — Python fallback.

Walks the validated final rule JSON and composes a short
plain-English summary (target: 300-400 tokens).

This is the **Python fallback** for trivial rules. Claude (the
`message` skill) writes the primary summary at Stage 6. The fallback
exists so trivial cases don't pay for an LLM call.

Strict rules:
- Never expose internal column / group / table / seed / template
  names.
- Never paraphrase a clarification question. If `clarification_question`
  is set on `state`, return it verbatim.
- Surface any warnings from the validate / parse stages.
"""

from __future__ import annotations

from typing import Any


def build_user_message(
    rule: dict[str, Any] | None,
    *,
    sentence: str | None = None,
    warnings: list[str] | None = None,
    state: Any | None = None,
) -> str:
    """Compose a short, marketer-facing summary.

    Precedence:
      1. If `state.clarification_question` is set → return it verbatim.
      2. If `rule` is empty or has no rule tree → return a generic
         success message.
      3. Otherwise walk the rule and compose a templated summary.
    """

    # 1. Clarification takes precedence.
    if state is not None and getattr(state, "clarification_question", None):
        return str(state.clarification_question)
    if sentence and not rule:
        # The user gave a sentence but no rule was emitted — surface
        # the clarification if available, else a generic prompt.
        return _generic_missing_message()

    if not rule:
        return _generic_missing_message()

    # 2. Walk the rule tree.
    detail = rule.get("detail", {}) if isinstance(rule, dict) else {}
    rules_root = detail.get("rules", {}) if isinstance(detail, dict) else {}
    children = rules_root.get("childrens", []) if isinstance(rules_root, dict) else []
    schedule = rules_root.get("schedule", {}) if isinstance(rules_root, dict) else {}

    target = _describe_audience(children)
    action = _describe_action(children)
    schedule_text = _describe_schedule(schedule)
    bonus = _describe_bonus(children)

    parts: list[str] = []
    parts.append(f"Your campaign targets {target}.")

    if action:
        parts.append(f"They'll receive {action}.")

    if bonus:
        parts.append(bonus)

    if schedule_text:
        parts.append(schedule_text)

    text = " ".join(parts).strip()

    if warnings:
        bullets = "\n".join(f"- {w}" for w in warnings if w)
        if bullets:
            text += "\n\nNotes:\n" + bullets

    return text


# ---------------------------------------------------------------------------
# Helpers — walk the tree, no LLM
# ---------------------------------------------------------------------------


def _describe_audience(children: list[dict[str, Any]]) -> str:
    """Return a one-clause description of the targeting."""

    if not children:
        return "the configured audience"

    # Walk the tree to collect leaf condition values.
    values: list[str] = []

    def walk(node: dict[str, Any]) -> None:
        t = node.get("type")
        if t == "condition":
            v = node.get("values", {})
            if isinstance(v, dict):
                if "value" in v:
                    values.append(_humanize_condition(node, v["value"]))
                elif "fromValue" in v and "toValue" in v:
                    values.append(_humanize_condition(node, [v["fromValue"], v["toValue"]]))
        elif t == "conditions":
            for c in node.get("childrens", []) or []:
                walk(c)

    for c in children:
        walk(c)

    if not values:
        return "the configured audience"

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            unique.append(v)

    if len(unique) == 1:
        return f"customers where {unique[0]}"
    return "customers matching " + " AND ".join(unique[:3])


def _humanize_condition(node: dict[str, Any], value: Any) -> str:
    """Convert a single condition leaf to a human phrase.

    Format: `column <op> value` with the column name humanized.
    """

    profile = node.get("profile", {}) if isinstance(node, dict) else {}
    raw_name = profile.get("name", "") if isinstance(profile, dict) else ""
    op = node.get("operator", "=")

    human_name = _humanize_kpi_name(raw_name)

    op_str = {
        "=": "is",
        "<>": "is not",
        ">": "is greater than",
        ">=": "is at least",
        "<": "is less than",
        "<=": "is at most",
        "between": "is between",
        "in": "is in",
        "not_in": "is not in",
        "is_null": "is null",
        "is_not_null": "is not null",
        "like": "matches",
    }.get(op, op)

    return f"{human_name} {op_str} {value}"


def _humanize_kpi_name(name: str) -> str:
    """Convert a SCREAMING_SNAKE_CASE KPI name to a human phrase."""

    if not name:
        return "audience"
    # Lowercase and join words.
    words = name.replace("_", " ").lower()
    return words


def _describe_action(children: list[dict[str, Any]]) -> str:
    """Return a one-clause description of the action."""

    action_node = _find_first(children, predicate=lambda n: n.get("type") == "action")
    if not action_node:
        return "the campaign action runs"

    action = action_node.get("action", {})
    name = action.get("name", "") if isinstance(action, dict) else ""
    request_fields = action_node.get("request", {}).get("field", [])
    msg = next((f.get("value") for f in request_fields if f.get("name") == "MESSAGE"), "")
    channel = next((f.get("value") for f in request_fields if f.get("name") == "CHANNEL"), "")

    if name == "Send Promotion":
        if channel:
            channel_lower = channel.lower()
            return f"a {channel_lower} with the message \"{msg}\"" if msg else f"a {channel_lower} campaign message"
        return f"the promotional message \"{msg}\"" if msg else "the promotional message"
    if msg:
        return f"the campaign action \"{msg}\""
    return f"the {name or 'campaign'} action"


def _describe_bonus(children: list[dict[str, Any]]) -> str:
    """Return a one-clause description of the bonus, or empty."""

    action_node = _find_first(children, predicate=lambda n: n.get("type") == "action")
    if not action_node:
        return ""

    bonus = action_node.get("bonus")
    if not bonus or not isinstance(bonus, dict):
        return ""

    criteria = bonus.get("criteria", [])
    if not criteria:
        return ""

    crit = criteria[0]
    action_type = crit.get("kpiEnglishName", "")
    value = crit.get("value", "")
    max_value = crit.get("maxValue", "")
    aggregation = crit.get("aggregation", "")
    no_of_days = crit.get("noOfDays", "")
    bonus_details = bonus.get("bonusDetails", [])
    benefit = bonus_details[0] if bonus_details else None

    parts: list[str] = []
    if action_type == "Recharge" and aggregation == "RANGE" and max_value:
        parts.append(f"If they recharge between {value} and {max_value}")
    elif action_type == "Recharge" and aggregation == "SUM" and value:
        parts.append(f"If they recharge more than {value}")
    elif action_type == "Recharge" and aggregation == "COUNT" and value:
        parts.append(f"If they recharge at least {value} times")
    else:
        parts.append("If the bonus trigger fires")

    if no_of_days and no_of_days != "0":
        parts.append(f"within {no_of_days} days")
    else:
        parts.append("after")

    if benefit:
        benefit_product = benefit.get("productId", "")
        # productId may be a numeric ID; don't expose it. Just say "the bonus benefit".
        parts.append("they also receive the bonus benefit")
    else:
        parts.append("they get the bonus")

    return ", ".join(parts) + "."


def _describe_schedule(schedule: dict[str, Any]) -> str:
    """Return a one-clause description of the schedule, or empty."""

    if not schedule:
        return ""
    fields = {f.get("name"): f.get("value") for f in schedule.get("field", [])}
    stype = fields.get("ScheduleType", "")
    if not stype:
        return ""

    if stype == "ScheduleNow":
        return "The campaign runs immediately."
    if stype == "Interval":
        d = fields.get("Days", "0")
        h = fields.get("Hours", "0")
        m = fields.get("Minutes", "0")
        every = []
        if d and d != "0":
            every.append(f"{d} day(s)")
        if h and h != "0":
            every.append(f"{h} hour(s)")
        if m and m != "0":
            every.append(f"{m} minute(s)")
        every_str = " ".join(every) if every else "the configured interval"
        start = fields.get("StartDate", "")
        end = fields.get("ExpiryDate", "")
        when = f" from {start} until {end}" if start and end else ""
        return f"The campaign runs every {every_str}{when}."
    if stype == "Daily":
        time_ = fields.get("Time") or fields.get("day", "")
        return f"The campaign runs daily at {time_}." if time_ else "The campaign runs daily."
    if stype == "Weekly":
        return f"The campaign runs weekly ({fields.get('Day', '')})."
    if stype == "Monthly":
        return f"The campaign runs monthly ({fields.get('Date') or fields.get('Day', '')})."
    return f"The campaign runs on schedule type {stype}."


def _find_first(
    nodes: list[dict[str, Any]],
    *,
    predicate,
) -> dict[str, Any] | None:
    """DFS for the first node matching the predicate."""

    stack = list(nodes or [])
    while stack:
        n = stack.pop()
        if predicate(n):
            return n
        for c in n.get("childrens", []) or []:
            stack.append(c)
    return None


def _generic_missing_message() -> str:
    return "We weren't able to build the rule. Could you rephrase the campaign statement?"