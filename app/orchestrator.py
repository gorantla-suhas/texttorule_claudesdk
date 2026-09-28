"""Orchestrator — drives a single Claude Agent SDK session per request.

The orchestrator:

1. builds the `ClaudeAgentOptions` from the project `.claude/`
   directory (skills, agents, hooks) and the runtime settings;
2. creates the in-process MCP server that exposes the rule tools
   (`app.tools.create_rule_server`);
3. streams the request into a `ClaudeSDKClient` and yields messages
   back to the FastAPI handler.

The orchestrator does **not** contain any business logic. It is a thin
adapter between FastAPI and the Claude Agent SDK. All reasoning is
performed by Claude via skills + MCP tools.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, AsyncIterator, Callable

from app.config import PROJECT_DIR, load_settings
from app.hooks import make_hooks
from app.logging import get_logger
from app.schemas import RuleState
from app.tools import create_rule_server


log = get_logger(__name__)
_stdlib_log = logging.getLogger(__name__)


DEBUG = os.environ.get("RULE_DEBUG", "0") == "1"


def _dbg(msg: str, **fields: Any) -> None:
    """Emit a debug log line if RULE_DEBUG=1."""

    if DEBUG:
        _stdlib_log.info(f"[orchestrator] {msg}", extra=fields)


# ---------------------------------------------------------------------------
# Orchestrator system prompt
# ---------------------------------------------------------------------------

ORCHESTRATOR_APPEND = """\
You are the orchestrator of the texttorule_engine. Convert one
natural-language telecom campaign statement into the intermediate
if-block string the downstream campaign engine consumes.

Available tools (all prefixed mcp__rule__):
  - extract_segment_markers    decide proceed / decompose / clarify
  - retrieve_kpis              find KPI column for each audience filter
  - lookup_action              pick Send Promotion + channel + message
  - lookup_schedule            pick schedule_type + dates
  - render_intermediate_rule   emit the if-block string
  - validate_intermediate_rule final technical check

Do NOT use Read, Glob, Grep, Bash, Write, Edit, or Skill. You do not
need to read files. Stay focused. Max 8 tool calls total.

Procedure (strict order):
  1. mcp__rule__extract_segment_markers   -- once
  2. mcp__rule__retrieve_kpis             -- AT MOST ONCE
     Pass slots as: {"metric": "<the audience phrase>", "filters": [], "time": "<time phrase or 'current'>"}
  3. mcp__rule__lookup_action             -- once
  4. mcp__rule__lookup_schedule           -- once
  5. mcp__rule__render_intermediate_rule  -- once
     EXACT if_blocks shape (no other shape is accepted):
       [
         {
           "branch": "if",
           "condition": {
             "predicates": [
               {"kpi": "<column_name from retrieve_kpis>", "operator": ">", "value": 50},
               {"kpi": "<column_name>", "operator": "=", "value": "prepaid"}
             ],
             "logic": "AND"
           },
           "action": {
             "action_name": "Send Promotion",
             "channel": "SMS",
             "product_id": "",
             "message": "<short promo phrase>"
           }
         }
       ]
     The kpi field MUST be the EXACT column_name from the
     retrieve_kpis response (or feature_name if column_name is empty).
     Operators MUST be one of: =, <>, >, >=, <, <=, BETWEEN, IN LIST.
     Multiple predicates join with AND/OR via logic.
  6. mcp__rule__validate_intermediate_rule -- once on the rendered string
  7. Stop. Your final assistant text is the rendered if-block string.

KPI picking rules (HARD CONSTRAINTS -- violations fail validation):
  - The kpi field in every predicate MUST be copied verbatim from a
    column_name or feature_name in a retrieve_kpis result. NEVER
    invent, paraphrase, or compose new column names.
  - If a candidate you pick has column_name empty, use feature_name
    instead (still verbatim from the result).
  - Prefer feature_name when MULTIPLE retrieve_kpis results share the
    same column_name but differ in time_window_value (e.g. M1, M3, 30D,
    60D, 90D). Choose the candidate whose time_window_value matches the
    user's time phrase ("last month" -> M1, "30 days" -> 30D, etc.) and
    use its feature_name. Only fall back to column_name when the
    feature_name is empty for that candidate.
  - Skip candidates that add unrequested qualifiers (prepaid, postpaid,
    IDD, roaming, onnet, offnet) unless the user asked for them.
  - For numeric thresholds use >, <, >=, <=. For equals use =.
  - For date phrases use BETWEEN with two values.
  - If validate returns an error about a fabricated kpi, call
    retrieve_kpis again with the exact metric phrase you want and use
    the first candidate's column_name (or feature_name).

If validate returns errors, fix the offending component and re-render.
At most twice. If still failing, return the error message as final text.
"""


# ---------------------------------------------------------------------------
# Agent / option builders
# ---------------------------------------------------------------------------

AGENTS_DIR = PROJECT_DIR / ".claude" / "agents"
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n?", re.S)


def load_agent_prompt(name: str) -> str:
    """Read an agent prompt from `.claude/agents/<name>.md`, stripping
    frontmatter.
    """

    path = AGENTS_DIR / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    return FRONTMATTER_RE.sub("", text).strip()


def build_agents(subagent_model: str) -> dict[str, Any]:
    """No subagents this round. Verifier was tied to bonus/parse stages
    which are removed."""

    return {}


def build_options(
    state: RuleState,
    *,
    debug_sdk: bool = False,
    stderr_callback: Callable[[str], None] | None = None,
) -> Any:
    """Build the `ClaudeAgentOptions` for one request."""

    from claude_agent_sdk import ClaudeAgentOptions

    settings = load_settings()
    extra_args = {"debug": "api,mcp,hooks"} if debug_sdk else {}
    return ClaudeAgentOptions(
        setting_sources=["project"],
        cwd=str(PROJECT_DIR),
        model=settings.orchestrator_model,
        system_prompt=ORCHESTRATOR_APPEND,
        allowed_tools=[
            "Agent",
            "mcp__rule__extract_segment_markers",
            "mcp__rule__retrieve_kpis",
            "mcp__rule__lookup_action",
            "mcp__rule__lookup_schedule",
            "mcp__rule__render_intermediate_rule",
            "mcp__rule__validate_intermediate_rule",
        ],
        disallowed_tools=["Bash", "Read", "Skill", "Glob", "Grep", "Write", "Edit"],
        skills="all",
        mcp_servers={"rule": create_rule_server(state)},
        agents=build_agents(settings.subagent_model),
        hooks=make_hooks(state),
        max_turns=settings.max_turns,
        include_hook_events=debug_sdk,
        stderr=stderr_callback,
        extra_args=extra_args,
    )


# ---------------------------------------------------------------------------
# Request driver
# ---------------------------------------------------------------------------


async def run_request(
    state: RuleState,
    *,
    debug_sdk: bool = False,
    stderr_callback: Callable[[str], None] | None = None,
) -> AsyncIterator[Any]:
    """Run the orchestrator session and yield messages."""

    from claude_agent_sdk import ClaudeSDKClient

    settings = load_settings()
    log.info("orchestrator: starting",
             request_id=state.request_id,
             client=state.client,
             model=settings.orchestrator_model,
             max_turns=settings.max_turns)

    prompt = (
        f"Client: {state.client}\n\n"
        f"Audience request:\n{state.sentence}\n\n"
        "Build the campaign rule. Follow the procedure in your "
        "system prompt. Return: the intermediate rule string as "
        "your final assistant text."
    )

    t0 = time.perf_counter()
    message_count = 0
    tool_call_count = 0
    last_tool_name = ""
    main_session_error = None

    try:
        async with ClaudeSDKClient(
            options=build_options(state, debug_sdk=debug_sdk, stderr_callback=stderr_callback)
        ) as sdk_client:
            _dbg("opening SDK client")
            await sdk_client.query(prompt)
            _dbg("prompt sent; awaiting response stream")
            async for message in sdk_client.receive_response():
                message_count += 1
                if DEBUG:
                    _log_message(message, message_count)
                tc = _extract_tool_name(message)
                if tc:
                    tool_call_count += 1
                    last_tool_name = tc
                    log.info("orchestrator: tool call",
                             request_id=state.request_id,
                             turn=message_count,
                             tool=tc)
                if _is_result_message(message):
                    duration_ms = _extract_duration_ms(message)
                    err = _extract_error(message)
                    log.info("orchestrator: result",
                             request_id=state.request_id,
                             turn=message_count,
                             is_error=bool(err),
                             error=err,
                             duration_ms=duration_ms)
                    if err:
                        main_session_error = err
                if DEBUG:
                    txt = _extract_text(message)
                    if txt:
                        log.info("orchestrator: assistant_text",
                                 request_id=state.request_id,
                                 turn=message_count,
                                 text=txt[:2000])
                yield message
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        log.exception("orchestrator: SDK session crashed",
                      request_id=state.request_id,
                      elapsed_ms=elapsed_ms,
                      tool_calls=tool_call_count,
                      last_tool=last_tool_name)
        raise

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    log.info("orchestrator: main session complete",
             request_id=state.request_id,
             elapsed_ms=elapsed_ms,
             messages=message_count,
             tool_calls=tool_call_count,
             last_tool=last_tool_name,
             has_intermediate=bool(state.intermediate_rule),
             main_session_error=main_session_error)


# ---------------------------------------------------------------------------
# Message extraction helpers
# ---------------------------------------------------------------------------


def _extract_tool_name(message: Any) -> str | None:
    """Return the tool name from an `AssistantMessage` if it has one."""

    content = getattr(message, "content", None)
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "tool_use":
                return str(block.get("name", ""))
        elif hasattr(block, "type") and getattr(block, "type", None) == "tool_use":
            return str(getattr(block, "name", ""))
        elif hasattr(block, "name") and not hasattr(block, "text"):
            return str(getattr(block, "name", ""))
    return None


def _is_result_message(message: Any) -> bool:
    """True for `UserMessage` containing a `tool_result` block."""

    cls = type(message).__name__
    if cls != "UserMessage":
        return False
    content = getattr(message, "content", None)
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                return True
            if hasattr(block, "type") and getattr(block, "type", None) == "tool_result":
                return True
    return False


def _extract_duration_ms(message: Any) -> int | None:
    """Extract `duration_ms` from a result message if present."""

    if not _is_result_message(message):
        return None
    content = getattr(message, "content", None)
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                d = block.get("duration_ms") or block.get("duration_api_ms")
                if d is not None:
                    return int(d)
            elif hasattr(block, "duration_ms"):
                d = getattr(block, "duration_ms", None)
                if d is not None:
                    return int(d)
    return None


def _extract_error(message: Any) -> str | None:
    """Return the error string from a tool_result block, if any."""

    if not _is_result_message(message):
        return None
    content = getattr(message, "content", None)
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if "is_error" in block and block.get("is_error"):
                    return str(block.get("content", "error"))
                err = block.get("error")
                if err:
                    return str(err)
    return None


def _extract_text(message: Any) -> str | None:
    """Concatenate all `text` blocks from a message into a single string."""

    if message is None:
        return None
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    out.append(str(block["text"]))
            elif hasattr(block, "text"):
                out.append(str(block.text))
        return "\n".join(out) if out else None
    return None


def _log_message(message: Any, n: int) -> None:
    """Debug-level log of one SDK message."""

    cls = type(message).__name__
    fields = {"cls": cls, "n": n}
    if hasattr(message, "subtype"):
        fields["subtype"] = getattr(message, "subtype", None)
    if hasattr(message, "stop_reason"):
        fields["stop_reason"] = getattr(message, "stop_reason", None)
    fields["text"] = (_extract_text(message) or "")[:2000]
    log.debug("orchestrator: sdk_message", **fields)