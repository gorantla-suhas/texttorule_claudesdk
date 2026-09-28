"""MCP tool package for the texttorule_engine.

`create_rule_server(state)` is the in-process MCP server the
orchestrator launches. Each `@tool` function below is a deterministic
Python operation exposed to the agent. None of these tools make
business decisions; the agent (Claude) owns those.

Tool surface used by the orchestrator + skills:

    Stage 1 (decompose, validation skill):
        extract_segment_markers    — candidate split positions

    Stage 2 (component selection, condition/action/schedule skills):
        retrieve_kpis              — KPI candidates per role
        lookup_action              — Send Promotion + channel from sentence
        lookup_schedule            — schedule_type from cadence phrase

    Stage 3 (parser skill):
        render_intermediate_rule   — components → if-block string

    Stage 4 (validation skill):
        validate_intermediate_rule — placeholder + operator + column check

The server is created per request so the audit dicts are request-scoped
and can be garbage collected when the request finishes.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.logging import get_logger
from app.schemas import RuleState

log = get_logger(__name__)


def _text_result(data: Any) -> dict[str, Any]:
    """Wrap a value in the MCP text-result envelope."""

    return {
        "content": [{"type": "text", "text": json.dumps(data, indent=2, sort_keys=True, default=str)}],
        "structuredContent": data,
    }


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_written_date(text: str) -> str | None:
    """Parse '10 February 2025' or 'February 10, 2025' to 'YYYY-MM-DD'."""

    s = (text or "").strip().rstrip(".")
    m = re.match(r"^(\d{1,2})\s+(\w+)\s+(\d{4})$", s)
    if m:
        d, month_name, y = m.group(1), m.group(2).lower(), int(m.group(3))
        if month_name in _MONTHS:
            return f"{y:04d}-{_MONTHS[month_name]:02d}-{int(d):02d}"
    m = re.match(r"^(\w+)\s+(\d{1,2}),?\s+(\d{4})$", s)
    if m:
        month_name, d, y = m.group(1).lower(), m.group(2), int(m.group(3))
        if month_name in _MONTHS:
            return f"{y:04d}-{_MONTHS[month_name]:02d}-{int(d):02d}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return s
    return None


def create_rule_server(state: RuleState):
    """Create the in-process MCP server for one request."""

    from claude_agent_sdk import create_sdk_mcp_server, tool

    # -----------------------------------------------------------------------
    # Stage 1 — evidence helper for decomposition
    # -----------------------------------------------------------------------

    @tool(
        "extract_segment_markers",
        "Return candidate split points in a marketer sentence. The validation skill uses these to decide proceed / decompose / clarify.",
        {
            "type": "object",
            "properties": {"sentence": {"type": "string"}},
            "required": ["sentence"],
        },
    )
    async def extract_segment_markers(args: dict[str, Any]) -> dict[str, Any]:
        from app.tools.extract_segment_markers import extract_segment_markers as _extract

        sentence = args.get("sentence", "") or ""
        markers = _extract(sentence)
        return _text_result({"sentence": sentence, "markers": markers})

    # -----------------------------------------------------------------------
    # Stage 2a — KPI retrieval (condition skill)
    # -----------------------------------------------------------------------

    @tool(
        "retrieve_kpis",
        "Retrieve KPI candidates by role (metric, filter, time). Returns up to top_k per role. Page 1 = top 5, page 2 = 6-10.",
        {
            "type": "object",
            "properties": {
                "slots": {"type": "object"},
                "client": {"type": "string"},
                "page": {"type": "integer", "minimum": 1, "maximum": 3},
            },
            "required": ["client"],
        },
    )
    async def retrieve_kpis(args: dict[str, Any]) -> dict[str, Any]:
        from app.tools.retrieve_kpis import retrieve_kpis as _retrieve

        slots = args.get("slots", {}) or {}
        client = args.get("client", "omantel")
        page = args.get("page") or 1
        log.info("tool: retrieve_kpis IN", slots=slots, page=page)
        try:
            result = _retrieve(slots, client=client, page=page)
        except Exception as exc:  # noqa: BLE001
            log.exception("tool: retrieve_kpis CRASHED", error=str(exc))
            return _text_result({
                "audit_id": "",
                "page": page,
                "candidates": {"metric": [], "filter": [], "time": []},
                "warnings": [f"retrieve_kpis crashed: {exc}"],
                "errors": [str(exc)],
            })
        # Record every returned candidate as an approved KPI for this
        # request. The validator will reject any `kpi` in the if-block
        # that isn't in this set or in kpis.csv directly.
        for role, cands in (result.get("candidates") or {}).items():
            for c in cands:
                cn = (c.get("column_name") or "").strip()
                fn = (c.get("feature_name") or "").strip()
                if cn:
                    state.approved_kpis.add(cn)
                if fn:
                    state.approved_kpis.add(fn)
        log.info("tool: retrieve_kpis OUT",
                 approved_kpis_count=len(state.approved_kpis),
                 candidates_metric_n=len((result.get("candidates") or {}).get("metric", [])),
                 warnings=result.get("warnings", []))
        return _text_result(result)

    # -----------------------------------------------------------------------
    # Stage 2b — action lookup (action skill)
    # -----------------------------------------------------------------------

    @tool(
        "lookup_action",
        "Resolve the action for a marketer sentence. This round only Send Promotion. Returns the channel from the sentence and the chosen action_type.",
        {
            "type": "object",
            "properties": {
                "sentence": {"type": "string", "description": "The full sentence. The tool extracts the channel (SMS / EMAIL / IN_APP / USSD) and validates 'Send Promotion' applies."},
                "client": {"type": "string"},
            },
            "required": ["sentence", "client"],
        },
    )
    async def lookup_action(args: dict[str, Any]) -> dict[str, Any]:
        """Return Send Promotion with channel inferred from the sentence."""

        sentence = args.get("sentence", "") or ""
        lowered = sentence.lower()

        # Channel inference.
        channel = "SMS"  # default per the README example
        for cand in ("email", "in_app", "in-app", "ussd", "push", "sms"):
            if cand in lowered:
                channel = cand.upper().replace("-", "_").replace("IN_APP", "IN_APP")
                break

        # Always "Send Promotion" this round.
        selected = {
            "action_name": "Send Promotion",
            "action_type": "send_sms",
            "channel": channel,
            "product_id": "",
            "message": "",
            "message_id": "",
        }

        # The marketer's free-text goal becomes MESSAGE if it looks
        # like a quoted string or a short noun phrase following the verb.
        quoted = re.search(r'"([^"]+)"', sentence)
        if quoted:
            selected["message"] = quoted.group(1).strip()

        log.info("tool: lookup_action",
                 request_id=state.request_id,
                 channel=channel,
                 has_message=bool(selected["message"]))
        return _text_result({"selected": selected, "channel_inferred": channel})

    # -----------------------------------------------------------------------
    # Stage 2c — schedule lookup (schedule skill)
    # -----------------------------------------------------------------------

    @tool(
        "lookup_schedule",
        "Resolve the schedule for a marketer sentence. Returns the 9-type catalog entry that matches the cadence phrase, and a ready-to-render schedule dict.",
        {
            "type": "object",
            "properties": {
                "sentence": {"type": "string", "description": "The full sentence. The tool extracts the cadence phrase (every N hours, every Monday, daily at HH:MM, etc.) and any date range."},
                "client": {"type": "string"},
            },
            "required": ["sentence", "client"],
        },
    )
    async def lookup_schedule(args: dict[str, Any]) -> dict[str, Any]:
        from app.tools.lookup_schedule import lookup_schedule as _lookup

        sentence = args.get("sentence", "") or ""
        client = args.get("client", "omantel")
        result = _lookup(sentence, client=client)
        log.info("tool: lookup_schedule",
                 request_id=state.request_id,
                 schedule_type=(result.get("selected") or {}).get("schedule_type"))
        return _text_result(result)

    # -----------------------------------------------------------------------
    # Stage 3 — render if-block (parser skill)
    # -----------------------------------------------------------------------

    @tool(
        "render_intermediate_rule",
        "Render the intermediate if-block string from component objects (condition predicates, action, schedule). The only legal emitter of the if-block syntax.",
        {
            "type": "object",
            "properties": {
                "if_blocks": {"type": "array", "items": {"type": "object"}},
                "schedule": {"type": "object"},
                "client": {"type": "string"},
            },
            "required": ["if_blocks", "client"],
        },
    )
    async def render_intermediate_rule(args: dict[str, Any]) -> dict[str, Any]:
        from app.tools.render_intermediate_rule import render_intermediate_rule as _render

        if_blocks = args.get("if_blocks", []) or []
        schedule = args.get("schedule")
        client = args.get("client", "omantel")
        log.info("tool: render_intermediate_rule IN",
                 if_blocks=json.dumps(if_blocks)[:1500],
                 schedule=json.dumps(schedule)[:500] if schedule else None)
        result = _render(if_blocks=if_blocks, schedule=schedule, client=client)
        log.info("tool: render_intermediate_rule OUT",
                 has_rule=bool(result.get("intermediate_rule")),
                 errors=result.get("errors", []))
        if result.get("intermediate_rule"):
            state.intermediate_rule = result["intermediate_rule"]
        return _text_result(result)

    # -----------------------------------------------------------------------
    # Stage 4 — validate if-block (validation skill)
    # -----------------------------------------------------------------------

    @tool(
        "validate_intermediate_rule",
        "Validate the emitted if-block against placeholder discipline, operator legality (operator_catalog.yaml), and column existence (KPI catalog).",
        {
            "type": "object",
            "properties": {
                "intermediate_rule": {"type": "string"},
                "client": {"type": "string"},
            },
            "required": ["intermediate_rule"],
        },
    )
    async def validate_intermediate_rule(args: dict[str, Any]) -> dict[str, Any]:
        from app.tools.validate_intermediate_rule import validate_intermediate_rule as _validate

        intermediate_rule = args.get("intermediate_rule", "") or ""
        client = args.get("client", "omantel")
        result = _validate(
            intermediate_rule,
            client=client,
            approved_kpis=state.approved_kpis,
        )
        state.intermediate_validation = result
        log.info("tool: validate_intermediate_rule",
                 request_id=state.request_id,
                 valid=result.get("valid"),
                 errors=result.get("errors", []))
        return _text_result(result)

    return create_sdk_mcp_server(
        name="rule",
        version="0.1.0",
        tools=[
            extract_segment_markers,
            retrieve_kpis,
            lookup_action,
            lookup_schedule,
            render_intermediate_rule,
            validate_intermediate_rule,
        ],
    )