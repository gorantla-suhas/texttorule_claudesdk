"""Render the intermediate if-block string from component objects.

Stage 3 implementation. Claude (the parser skill) calls this tool
to emit the canonical if-block string per the contract in
`.claude/skills/parser/references/intermediate-rule.md`.

This module is pure Python — no LLM, no DB. It takes already-resolved
component objects and produces the if-block string with correct
quoting, field order, and operator syntax.

It is the **only** legal emitter of the if-block syntax. Claude must
not hand-write it.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Value formatting
# ---------------------------------------------------------------------------


def _fmt_value(v: Any) -> str:
    """Format a single value for inclusion in an if-block.

    - str  → "..."
    - bool → "True" / "False"
    - None → ""
    - int/float → str(v)
    - list → comma-separated, each item recursively formatted
    - dict → JSON-ish "{k=v;k=v}" (used for benefit details, start_time,
      end_time, time_window-like dicts)
    """

    if v is None:
        return ""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, list):
        return ", ".join(_fmt_value(item) for item in v)
    if isinstance(v, dict):
        return "{" + "; ".join(f"{k}={_fmt_value(val)}" for k, val in v.items()) + "}"
    return f'"{str(v)}"'


def _fmt_kv(k: str, v: Any) -> str:
    """Format a key=value pair for inside action(…) or schedule(…)."""

    return f"{k}={_fmt_value(v)}"


# ---------------------------------------------------------------------------
# Condition rendering
# ---------------------------------------------------------------------------


def _render_predicate(pred: dict[str, Any]) -> str:
    """Render one predicate like `KPI > 10` or `KPI BETWEEN 6 AND 10`.

    Input shape:
        { "kpi": "<column_name>", "operator": "...", "value": <resolved> }
    """

    kpi = pred.get("kpi", "")
    op = pred.get("operator", "=")
    val = pred.get("value")

    op_lower = str(op).strip().lower()

    if op_lower == "between":
        if isinstance(val, (list, tuple)) and len(val) >= 2:
            lo, hi = val[0], val[1]
            return f"{kpi} BETWEEN {_fmt_value(lo)} AND {_fmt_value(hi)}"
        # Fall back: just one value
        return f"{kpi} BETWEEN {_fmt_value(val)} AND {_fmt_value(val)}"

    if op_lower in ("in", "in list", "in_list"):
        if isinstance(val, (list, tuple)):
            return f"{kpi} IN LIST({', '.join(_fmt_value(x) for x in val)})"
        return f"{kpi} IN LIST({_fmt_value(val)})"

    if op_lower in ("not_in", "not in", "not_in_list"):
        if isinstance(val, (list, tuple)):
            return f"{kpi} NOT IN LIST({', '.join(_fmt_value(x) for x in val)})"
        return f"{kpi} NOT IN LIST({_fmt_value(val)})"

    if op_lower in ("is_null",):
        return f"{kpi} IS NULL"

    if op_lower in ("is_not_null",):
        return f"{kpi} IS NOT NULL"

    if op_lower == "like":
        return f"{kpi} LIKE {_fmt_value(val)}"

    # Standard operators: =, <>, >, <, >=, <=
    return f"{kpi} {op} {_fmt_value(val)}"


def _render_condition(cond: dict[str, Any]) -> str:
    """Render a full condition (multiple predicates joined by logic).

    Input shape:
        {
          "predicates": [<pred>, ...]  OR  {"item": [<pred>, ...]}  OR
                        {"item": <single-pred-dict>}
          "logic": "AND" | "OR"      # default "AND"
        }

    Tolerates the model wrapping the list in {"item": [...]} or
    returning a single predicate as a dict (we wrap it in a list).
    """

    predicates = cond.get("predicates", []) or []
    # Model sometimes wraps the list in {"item": [...]}. Accept both.
    if isinstance(predicates, dict):
        inner = predicates.get("item") or predicates.get("predicates") or {}
        if isinstance(inner, dict):
            # Single predicate-as-dict. Wrap in a list.
            predicates = [inner]
        elif isinstance(inner, list):
            predicates = inner
        else:
            predicates = []
    logic = (cond.get("logic") or "AND").upper()

    rendered = [_render_predicate(p) for p in predicates]
    if not rendered:
        return ""

    inner = f" {logic} ".join(rendered)
    if len(rendered) > 1:
        return f"({inner})"
    return inner


# ---------------------------------------------------------------------------
# Action rendering
# ---------------------------------------------------------------------------


def _render_bonus_criteria(bc: dict[str, Any]) -> str:
    """Render the BONUS_CRITERIA block inside an action."""

    parts: list[str] = []

    # action_type (required)
    parts.append(_fmt_kv("action_type", bc.get("action_type", "Recharge")))

    # value (required, numeric)
    parts.append(_fmt_kv("value", bc.get("value", 0)))

    # aggregation (required)
    parts.append(_fmt_kv("aggregation", bc.get("aggregation", "SUM")))

    # max_value (only meaningful for RANGE)
    if bc.get("aggregation") == "RANGE":
        parts.append(_fmt_kv("maxValue", bc.get("max_value", 0)))

    # Optional fields with defaults.
    if bc.get("no_of_times") is not None and bc.get("no_of_times") != 1:
        parts.append(_fmt_kv("noOfTimes", bc["no_of_times"]))
    if bc.get("bonus_threshold") is not None and bc.get("bonus_threshold") != 1:
        parts.append(_fmt_kv("bonusThreshold", bc["bonus_threshold"]))
    if bc.get("no_of_days") is not None and bc.get("no_of_days") != 0:
        parts.append(_fmt_kv("noOfDays", bc["no_of_days"]))

    # Benefits list — empty list means no-op; still rendered as [].
    benefits = bc.get("benefits", []) or []
    parts.append(f"benefits=[{_render_benefits_inline(benefits)}]")

    return "{" + ", ".join(parts) + "}"


def _render_benefits_inline(benefits: list[dict[str, Any]]) -> str:
    """Render a list of benefit objects inline (one-liner)."""

    if not benefits:
        return ""

    rendered_items: list[str] = []
    for b in benefits:
        btype = b.get("type", "telco_product")
        details = b.get("details", {})
        success = b.get("success_message", "")
        error = b.get("error_message", "")

        parts = [
            _fmt_kv("type", btype),
            # details is itself a dict; _fmt_value wraps it in braces.
            f"details={_fmt_value(details) if isinstance(details, dict) else _fmt_value(details)}",
            _fmt_kv("success_message", success),
            _fmt_kv("error_message", error),
        ]
        rendered_items.append("{" + ", ".join(parts) + "}")

    return ", ".join(rendered_items)


def _render_action(action: dict[str, Any]) -> str:
    """Render the inside of `action(...)`."""

    parts: list[str] = []

    name = action.get("action_name", "Send Promotion")
    parts.append(_fmt_kv("ActionName", name))

    channel = action.get("channel", "SMS")
    if channel:
        parts.append(_fmt_kv("CHANNEL", str(channel).upper()))

    pid = action.get("product_id", "")
    parts.append(_fmt_kv("PRODUCT_ID", pid))

    msg = action.get("message", "")
    parts.append(_fmt_kv("MESSAGE", msg))

    mid = action.get("message_id", "")
    if mid:
        parts.append(_fmt_kv("MESSAGE_ID", mid))

    # Point Accumulation fields (reserved — emit only if non-empty).
    rb = action.get("reward_bucket", "")
    if rb:
        parts.append(_fmt_kv("Reward_Bucket", rb))
    mult = action.get("multiplier", "")
    if mult:
        parts.append(_fmt_kv("Multiplier", mult))
    rp = action.get("reward_point", "")
    if rp:
        parts.append(_fmt_kv("Reward_Point", rp))
    pv = action.get("point_validity", "")
    if pv:
        parts.append(_fmt_kv("Point_Validity", pv))

    # Bonus criteria (if present).
    bc = action.get("bonus_criteria")
    if bc:
        parts.append(f"BONUS_CRITERIA={_render_bonus_criteria(bc)}")

    return "action(" + ", ".join(parts) + ")"


# ---------------------------------------------------------------------------
# Schedule rendering
# ---------------------------------------------------------------------------


def _render_schedule(sched: dict[str, Any]) -> str:
    """Render the schedule(...) block in canonical field order."""

    parts: list[str] = []

    # Required first.
    parts.append(_fmt_kv("schedule_type", sched.get("schedule_type", "ScheduleNow")))

    # Canonical field order per `data/sdk_context/schedule`.
    for key in ("repeat", "last_fetch", "segment_rule_start_date", "segment_rule_end_date"):
        v = sched.get(key)
        if v is not None:
            parts.append(_fmt_kv(key, v))

    for key in ("interval", "frequency", "hours", "minutes"):
        v = sched.get(key)
        if v is not None and v != "":
            parts.append(_fmt_kv(key, v))

    # type (null for most; "First"/"Second"/"Third"/"Fourth"/"Last" for MonthlyWithSpecifics)
    t = sched.get("type")
    if t is not None:
        parts.append(_fmt_kv("type", t))

    for key in ("period", "week", "day"):
        v = sched.get(key)
        if v is not None and v != "":
            parts.append(_fmt_kv(key, v))

    # select_days — list of weekday names (3-letter caps) or numeric day-of-month
    sd = sched.get("select_days")
    if sd is not None:
        parts.append(f"select_days={_fmt_value(sd)}")

    # start_time / end_time — dict of {day_key: "HH:MM"}
    st = sched.get("start_time")
    if st is not None:
        parts.append(f"start_time={_fmt_value(st)}")

    et = sched.get("end_time")
    if et is not None:
        parts.append(f"end_time={_fmt_value(et)}")

    return "schedule(" + ", ".join(parts) + ")"


# ---------------------------------------------------------------------------
# Top-level render
# ---------------------------------------------------------------------------


def render_intermediate_rule(
    if_blocks: list[dict[str, Any]],
    schedule: dict[str, Any] | None,
    client: str,
) -> dict[str, Any]:
    """Render the if-block string from the component objects.

    Inputs:

        if_blocks: list of
            {
              "branch": "if" | "else_if",
              "condition": {
                "predicates": [...],
                "logic": "AND" | "OR"
              },
              "action": {
                "action_name": "Send Promotion",
                "channel": "SMS",
                "product_id": "",
                "message": "",
                "message_id": "",
                "bonus_criteria": {...} | null
              }
            }

        schedule: dict in the 9-type schema (optional but recommended;
            one per statement, shared across all branches)

        client: client identifier (string)

    Returns:

        {
          "intermediate_rule": "<if-block string>",
          "warnings": []
        }
    """

    if not if_blocks:
        return {"intermediate_rule": "", "warnings": ["no if_blocks provided"], "errors": []}

    warnings: list[str] = []
    errors: list[str] = []

    blocks_rendered: list[str] = []
    for idx, ib in enumerate(if_blocks):
        branch = ib.get("branch", "if" if idx == 0 else "else_if")
        if branch not in ("if", "else_if"):
            errors.append(f"block {idx}: branch must be 'if' or 'else_if', got {branch!r}")
            continue

        cond_str = _render_condition(ib.get("condition", {}))
        action_str = _render_action(ib.get("action", {}))

        if branch == "if":
            blocks_rendered.append(f"if ( {cond_str} ) {{\n  {action_str}\n}}")
        else:
            blocks_rendered.append(f"else if ( {cond_str} ) {{\n  {action_str}\n}}")

    rule_body = "\n".join(blocks_rendered)

    schedule_str = ""
    if schedule is not None:
        schedule_str = _render_schedule(schedule)
        rule_body = rule_body + "\n" + schedule_str

    full = f"# client: {client}\n{rule_body}".strip()

    return {"intermediate_rule": full, "warnings": warnings, "errors": errors}


__all__ = ["render_intermediate_rule"]