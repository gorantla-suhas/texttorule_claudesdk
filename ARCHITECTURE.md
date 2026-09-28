# Architecture

> System design and request lifecycle for the texttorule_engine.
> Audience: maintainers, reviewers, and operators. Not loaded into Claude's
> context at runtime.

---

## Bird's-eye view

The engine converts a single natural-language telecom campaign sentence into
a structured `Rule JSON` that the downstream campaign engine consumes. Every
request flows through one **Claude Agent SDK session** that drives a Python
**MCP tool server** in-process. Claude reasons; Python executes.

```
┌──────────────────────────────────────────────────────────────────────┐
│                        HTTP boundary (FastAPI)                        │
│                                                                       │
│   POST /rule/build  ──►  app.api:build_rule  ──►  RuleState           │
│                                                                       │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Orchestrator (Claude SDK session)                 │
│                                                                       │
│   .claude/CLAUDE.md       ← project memory (skills, agents, rules)  │
│   .claude/skills/*        ← procedural memory per stage              │
│   .claude/agents/*        ← subagent definitions (builder, verifier) │
│   ORCHESTRATOR_APPEND     ← per-stage procedure (in code)            │
│                                                                       │
│   Model: minimax-m3:cloud via Ollama (ANTHROPIC_BASE_URL)            │
│                                                                       │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │ in-process MCP
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│              app.tools.create_rule_server(state)                      │
│                                                                       │
│   Stage 1: extract_segment_markers                                   │
│   Stage 2: retrieve_kpis · lookup_action · lookup_schedule           │
│   Stage 3: render_intermediate_rule                                  │
│   Stage 4: validate_intermediate_rule                                │
│                                                                       │
│   State writes (request-scoped RuleState):                            │
│     - approved_kpis          ← every retrieved KPI                   │
│     - intermediate_rule      ← emitted if-block string               │
│     - intermediate_validation ← validator verdict                     │
│                                                                       │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Deterministic Python                           │
│                                                                       │
│   configs/*.yaml     ← business config (operators, actions, etc.)   │
│   data/kpis.csv      ← single source of truth for KPIs (1,277 rows) │
│   app/services/*     ← catalog_lookup (operator legality etc.)       │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. HTTP boundary — `app/api.py`

| Concern | Where |
|---|---|
| Request validation | `RuleBuildRequest` (Pydantic, `client: Literal["omantel","airtel"]`) |
| Per-request state | `RuleState` dataclass, request-scoped, garbage-collected at end |
| Hard timeout | `RULE_REQUEST_TIMEOUT` (default 90 s) wraps the SDK session in `asyncio.wait_for` |
| Error envelope | `_error_response` — never raises; always returns a `RuleBuildResponse` |

### 2. Orchestrator — `app/orchestrator.py`

| Concern | Where |
|---|---|
| `ClaudeAgentOptions` builder | `build_options(state)` |
| `ORCHESTRATOR_APPEND` | Strict 7-step procedure (extract → retrieve → lookup action → lookup schedule → render → validate → emit) |
| Subagents | `build_agents(...)` returns `{}` — see "Subagents" below |
| Message extraction helpers | `_extract_tool_name`, `_extract_text`, `_is_result_message`, `_extract_error` |
| Stream driver | `run_request(state)` — yields SDK messages back to the API layer |

### 3. MCP tool server — `app/tools/__init__.py`

In-process MCP server (`create_sdk_mcp_server`) registered as `mcpServers.rule`
in `.claude/settings.json`. Six tools, all decorated with `@tool`:

| Tool | Stage | What it writes to `state` |
|---|---|---|
| `extract_segment_markers` | 1 | (read-only) |
| `retrieve_kpis` | 2 | `state.approved_kpis` |
| `lookup_action` | 2 | (read-only) |
| `lookup_schedule` | 2 | (read-only) |
| `render_intermediate_rule` | 3 | `state.intermediate_rule` |
| `validate_intermediate_rule` | 4 | `state.intermediate_validation` |

Each tool's Python implementation lives in `app/tools/<name>.py`. The
`__init__.py` is the wire-up; the implementations are pure Python and have no
business decisions.

### 4. Catalog and config

```
configs/
  operator_catalog.yaml      operator legality per data_type
  action_catalog.yaml        action types (Send Promotion, ...)
  bonus_catalog.yaml         bonus types + aggregations
  schedule_catalog.yaml      9 schedule types
  policy_catalog.yaml        eligibility / exclusion / conflict rules (deferred)
  clients.yaml               multi-tenant config
  common_prompts.yaml        shared prompt fragments

data/
  kpis.csv                   1,277 rows; single source of truth for KPIs
  sdk_context/               development reference (NOT read at runtime)
```

### 5. Project memory — `.claude/`

| File | Purpose |
|---|---|
| `CLAUDE.md` | Project-level context for Claude (loaded via `setting_sources=["project"]`) |
| `settings.json` | `ClaudeAgentOptions` defaults: model, permissions, hooks, MCP servers, agents |
| `skills/<name>/SKILL.md` | Per-stage procedural memory (validation, condition, action, bonus, schedule, parser, message, policy-stub) |
| `agents/builder.md` | Builder subagent definition (one final render + validate) |
| `agents/verifier.md` | Verifier subagent definition (semantic reader; reads `data/kpis.csv`) |

---

## Request lifecycle

```
T+0.000s   POST /rule/build received
           app.api:build_rule
             ├─ Build RuleState(request_id, client, sentence)
             └─ Wrap SDK session in asyncio.wait_for(timeout=90s)

T+0.020s   app.orchestrator.run_request(state)
             ├─ ClaudeAgentOptions built from .claude/ + ORCHESTRATOR_APPEND
             ├─ In-process MCP server created with state
             └─ async with ClaudeSDKClient(options)

T+0.5s     SDK streams response messages back. For each message:
             ├─ _extract_tool_name → log "orchestrator: tool call"
             ├─ _extract_error    → log "orchestrator: result"
             └─ yield             → API layer logs throughput

T+5–60s    Claude drives the 6 tools:
             1. extract_segment_markers    (1 call)
             2. retrieve_kpis              (1–N calls; populates approved_kpis)
             3. lookup_action              (1 call)
             4. lookup_schedule            (1 call)
             5. render_intermediate_rule   (1–N calls; writes intermediate_rule)
             6. validate_intermediate_rule (1 call on the emitted string)

T+~20s     Main session ends.
           app.api._run_agentic assembles the response:
             ok = state.intermediate_rule is not None and not empty
             final_rule_json, user_message, validation_verdict populated
             from state if available (else null)

T+~20s     RuleBuildResponse returned. HTTP 200.
```

---

## Invariants

1. **KPI CSV is the single source of truth** for KPIs. Do not duplicate
   column/group/operator metadata into skills, YAML, or `data/sdk_context/`.
2. **YAML holds business config only.** No KPI metadata; no secrets.
3. **Environment variables hold secrets + runtime settings only.** No
   business config in env.
4. **`render_intermediate_rule` is the only legal emitter** of the if-block
   syntax. Claude must not hand-write the string.
5. **Validation is mandatory.** Every emitted rule is passed to
   `validate_intermediate_rule`. Render or grammar failures are code defects,
   not prompts for the model to hand-edit.
6. **Shared `RuleState` is request-scoped.** Tools read/write fields on a
   per-request `RuleState`. The orchestrator decides what to put in it;
   Python only persists it.
7. **Every emitted KPI must be catalog-proven.** The validator rejects any
   `kpi` field in a predicate that is neither in `data/kpis.csv` nor in the
   `approved_kpis` set populated by `retrieve_kpis` for this request.

---

## Subagents

`builder.md` and `verifier.md` exist in `.claude/agents/`, but
`build_agents(...)` in `app/orchestrator.py` currently returns `{}`. The
subagents are **defined but not wired**. This is a known gap; it does not
block the core 6-stage pipeline because the orchestrator calls the MCP tools
directly.

To wire the subagents:

1. `build_agents(subagent_model)` should return:
   ```python
   {
     "builder":  AgentDefinition(model=..., prompt_file=".claude/agents/builder.md",  tools=[...], max_turns=3),
     "verifier": AgentDefinition(model=..., prompt_file=".claude/agents/verifier.md", tools=[...], max_turns=5),
   }
   ```
2. `mcp__rule__render_rule` and `mcp__rule__validate_rule` (the tools the
   agent prompts reference) must be registered in `app/tools/__init__.py`.
   Their Python implementations already exist at `app/tools/render.py` and
   `app/tools/validate.py`.
3. The orchestrator's `ORCHESTRATOR_APPEND` should `Agent(builder, ...)`
   after Stage 4 and `Agent(verifier, ...)` on comparison/uplift/downlift
   queries or low-confidence cases.

---

## Failure modes and how the API responds

| Failure | Where caught | API behavior |
|---|---|---|
| SDK session times out | `asyncio.wait_for` in `_run_agentic` | `ok=false, failure_reason="orchestrator did not emit an intermediate rule"` (timeout path) |
| Tool raises | `tool: retrieve_kpis CRASHED` log; tool returns error envelope | Tool result contains `errors:[…]`; Claude can retry |
| Validator rejects fabricated KPI | `validate_intermediate_rule` returns `valid=false` | Claude sees error in tool result and re-renders |
| Model hallucinates tool errors | (no catch — model-level issue) | `ok=false, failure_reason="orchestrator did not emit an intermediate rule"` |
| HTTP exception | `app.api.build_rule` `except` branch | Returns `RuleBuildResponse(ok=False, errors=[…])` with the exception message |

The HTTP layer **never raises**. Every request gets a structured
`RuleBuildResponse`, even on failure.

---

## Request ID and audit trail

- `state.request_id` is generated at the HTTP boundary (`req-<12 hex chars>`).
- `state.session_id` defaults to `rule-<client>`.
- `state.audit_log` accumulates every tool call's input and output (TODO —
  not yet wired in all tools).
- Logs are emitted as structured JSON via `app/logging.py` (structlog +
  stdlib). Go to `logs/` for the file sink; stdout for the live stream.

---

## Configuration knobs

| Env var | Default | What it controls |
|---|---|---|
| `RULE_ORCHESTRATOR_MODEL` | `claude-sonnet-4.5` (per `.claude/settings.json`) | Orchestrator LLM |
| `RULE_SUBAGENT_MODEL` | `claude-haiku-4.5` | Subagent LLM (unused — see "Subagents") |
| `RULE_MAX_TURNS` | `25` | Max turns in one SDK session |
| `RULE_REQUEST_TIMEOUT` | `90` | Hard timeout per request (seconds) |
| `RULE_VERIFIER_MODE` | `none` | `none` / `per-step` / `end-only` (declared, not yet invoked) |
| `RULE_DEBUG` | `0` | When `1`, dump assistant text and per-tool payloads to logs |
| `ANTHROPIC_BASE_URL` | (unset) | Ollama endpoint. SDK reads it natively. |
| `ANTHROPIC_API_KEY` | (unset) | Placeholder (`ollama`); SDK reads natively |
| `DB_HOST` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | (unset) | pyodbc credentials (read by SQL lookup tools) |

---

## Why this design

- **Claude thinks, Python executes.** The orchestrator never encodes
  business logic — it owns reasoning, slot shaping, and call ordering.
  Python tools are evidence, not decision-makers.
- **One legal emitter for the if-block syntax.** All canonical strings come
  out of `render_intermediate_rule`. The validator owns the grammar.
- **Validator enforces catalog provenance.** The local Ollama model can
  fabricate column names when it sees a low-relevance catalog. The validator
  closes that gap by hard-erroring on any KPI not in `kpis.csv` or in the
  approved set from `retrieve_kpis` for this request.
- **In-process MCP.** No separate tool server process to manage; request-
  scoped state lives in the same Python process as FastAPI.
