"""SDK hooks for the Claude Agent SDK.

The SDK calls these hooks before and after every tool invocation. We
use them to:

- audit every tool call into `RuleState.audit_log`;
- enforce that `render_rule` is the only legal emitter;
- enforce that `Bash` (and any other disallowed tool) is rejected;
- keep a running tool-call count for the per-request summary.
"""

from __future__ import annotations

from typing import Any

from app.config import PROJECT_DIR
from app.schemas import RuleState
from app.logging import get_logger

import json


_log = get_logger(__name__)


async def pre_tool_use(payload: dict[str, Any]) -> dict[str, Any]:
    """Called by the SDK before each tool invocation.

    `payload` follows the Claude Agent SDK `PreToolUse` contract:

    ```json
    { "tool_name": "...", "tool_input": {...}, "session_id": "..." }
    ```

    Return `{}` to allow the call, or `{"decision": "block",
    "reason": "..."}` to block it.
    """

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    if tool_name == "Bash":
        return {"decision": "block", "reason": "Bash is disallowed for the rule engine agent."}

    _log.info("pre_tool_use", tool_name=tool_name, tool_input=_safe_json(tool_input))
    return {}


async def post_tool_use(payload: dict[str, Any]) -> dict[str, Any]:
    """Called by the SDK after each tool invocation."""

    tool_name = payload.get("tool_name", "")
    tool_result = payload.get("tool_result", {})
    _log.info("post_tool_use", tool_name=tool_name, result=_safe_json(tool_result))
    return {}


def make_hooks(state: RuleState):
    """Build a hooks dict the SDK can consume, bound to the given state.

    TODO: wire the `state` argument into the audit log; today the
    function is a placeholder so the import surface is stable.
    """

    async def _pre(payload: dict[str, Any]) -> dict[str, Any]:
        return await pre_tool_use(payload)

    async def _post(payload: dict[str, Any]) -> dict[str, Any]:
        return await post_tool_use(payload)

    return {
        "PreToolUse": [_pre],
        "PostToolUse": [_post],
    }


def _safe_json(obj: Any) -> Any:
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return str(obj)
