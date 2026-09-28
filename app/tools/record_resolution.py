"""Resolution audit recorder.

A thin wrapper that appends an audit record to `RuleState.audit_log`.
The orchestrator calls this after every semantic decision so we can
replay and inspect what the agent did.
"""

from __future__ import annotations

from typing import Any

from app.schemas import RuleState


def record_resolution(state: RuleState, **fields: Any) -> None:
    """Append a structured audit record to the request state."""

    state.audit_log.append(fields)
