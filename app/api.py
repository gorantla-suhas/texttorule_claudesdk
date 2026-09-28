"""FastAPI HTTP boundary.

Routes:

- `GET  /health`       — liveness check.
- `GET  /observability` — non-secret Langfuse / variant status.
- `POST /rule/build`   — main endpoint; runs the orchestrator and
                         returns the `RuleBuildResponse`.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException

from app.config import load_settings
from app.logging import get_logger
from app.observability import (
    configure_langfuse,
    langfuse_status,
    observation,
    record_exception,
    update_observation,
)
from app.orchestrator import run_request
from app.schemas import RuleBuildRequest, RuleBuildResponse, RuleState


log = get_logger(__name__)
_stdlib_log = logging.getLogger(__name__)


configure_langfuse()
settings = load_settings()

app = FastAPI(
    title="texttorule_engine",
    description="Telecom rule engine: NL → intermediate if-block → final id/pid tree (Claude SDK centric).",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/observability")
async def observability() -> dict[str, Any]:
    return {"variant": "agent", "langfuse": langfuse_status()}


@app.post("/rule/build", response_model=RuleBuildResponse)
async def build_rule(request: RuleBuildRequest) -> RuleBuildResponse:
    """Build a Rule JSON from a natural-language sentence."""

    request_id = request.request_id or f"req-{uuid.uuid4().hex[:12]}"
    session_id = request.session_id or f"rule-{request.client}"
    user_id = request.user_id or "local-api"

    state = RuleState(
        request_id=request_id,
        client=request.client,
        sentence=request.sentence,
    )

    log.info("api: request received",
             request_id=request_id,
             client=request.client,
             sentence_len=len(request.sentence),
             session_id=session_id)

    trace_name = f"rule-build:{request.client}:{request_id}"
    t0 = time.perf_counter()
    with observation(
        trace_name,
        **{
            "langfuse.user.id": user_id,
            "langfuse.session.id": session_id,
            "langfuse.tags": ["rule-engine", request.client],
            "input.value": request.sentence,
            "rule.request_id": request_id,
            "rule.orchestrator_model": settings.orchestrator_model,
            "rule.subagent_model": settings.subagent_model,
            "rule.client": request.client,
            "rule.mode": "agent",
        },
    ) as span:
        try:
            response = await _run_agentic(request, state)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            log.exception("api: orchestrator failed",
                          request_id=request_id,
                          elapsed_ms=elapsed_ms)
            record_exception(span, exc)
            return _error_response(request, state, str(exc))
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        log.info("api: response ready",
                 request_id=request_id,
                 elapsed_ms=elapsed_ms,
                 ok=response.ok,
                 has_intermediate=bool(response.intermediate_rule),
                 has_final_json=bool(response.final_rule_json),
                 has_user_message=bool(response.user_message),
                 warnings=len(response.warnings or []))
        update_observation(
            span,
            **{
                "rule.ok": response.ok,
                "rule.emitted": response.final_rule_json is not None,
                "rule.selected_columns": response.selected_columns,
                "rule.warnings": response.warnings,
                "rule.pipeline_mode": "agent-sdk",
                "output.value": response.final_rule_json or response.failure_reason,
            },
        )
        return response


def _error_response(
    request: RuleBuildRequest,
    state: RuleState,
    message: str,
) -> RuleBuildResponse:
    """Build an error response when the orchestrator fails."""

    return RuleBuildResponse(
        ok=False,
        request_id=state.request_id,
        session_id=f"rule-{request.client}",
        orchestrator_model=settings.orchestrator_model,
        subagent_model=settings.subagent_model,
        client=request.client,
        sentence=request.sentence,
        failure_reason=message,
        errors=[message],
    )


# ---------------------------------------------------------------------------
# Agentic path (Claude Agent SDK session — primary)
# ---------------------------------------------------------------------------


async def _run_agentic(request: RuleBuildRequest, state: RuleState) -> RuleBuildResponse:
    """Stream a single Claude Agent SDK session and assemble the response.

    Hard-caps the SDK session at `RULE_REQUEST_TIMEOUT` seconds (default
    90) so a runaway Claude loop can't hang the HTTP request
    indefinitely. On timeout, we assemble a structured error
    response — we never raise.
    """

    import asyncio

    session_id = f"rule-{request.client}"
    timeout_s = int(os.environ.get("RULE_REQUEST_TIMEOUT", "90"))

    async def _drive_session() -> None:
        # Stream the orchestrator session. The MCP tools Claude calls
        # during the session write directly to `state`.
        async for _message in run_request(state):
            pass

    log.info("api: starting SDK session",
             request_id=state.request_id,
             timeout_s=timeout_s,
             verifier_mode=os.environ.get("RULE_VERIFIER_MODE", "none"))
    try:
        await asyncio.wait_for(_drive_session(), timeout=timeout_s)
    except asyncio.TimeoutError:
        log.warning("api: SDK session timed out",
                    request_id=state.request_id,
                    timeout_s=timeout_s,
                    has_intermediate=bool(state.intermediate_rule),
                    has_final_json=bool(state.final_rule_json))
        # Don't raise; assemble error response below.

    # Assemble the response from `state`.
    ok = state.intermediate_rule is not None and state.intermediate_rule.strip() != ""
    if not ok and not state.needs_clarification:
        ok = False
        failure_reason = state.failure_reason or "orchestrator did not emit an intermediate rule"
    else:
        failure_reason = state.failure_reason

    return RuleBuildResponse(
        ok=ok,
        request_id=state.request_id,
        session_id=session_id,
        orchestrator_model=settings.orchestrator_model,
        subagent_model=settings.subagent_model,
        client=request.client,
        sentence=request.sentence,
        intermediate_rule=state.intermediate_rule,
        final_rule_json=state.final_rule_json,
        validation_verdict=state.validation_verdict if state.validation_verdict in ("proceed", "clarify", "decompose") else None,
        clarification_question=state.clarification_question,
        user_message=state.user_message,
        selected_columns=[],   # populated by condition skill
        selected_products=[],  # populated by bonus / benefit skill
        needs_clarification=state.needs_clarification,
        failure_reason=failure_reason if not ok else None,
        warnings=state.warnings,
        errors=state.errors,
        diagnostics={
            "verifier_used": state.verifier_used,
            "verifier_report": state.verifier_report,
            "audit_log_size": len(state.audit_log),
        } if (state.verifier_used or state.verifier_report or state.audit_log) else None,
    )