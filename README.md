# texttorule_engine

Telecom rule engine: converts natural-language campaign rules into structured
Rule JSON via a six-stage Claude-driven pipeline.

**Architecture:** Claude SDK centric. Claude reasons, Python executes.
See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full request lifecycle,
component map, invariants, and failure modes.

---

## Layout

```
.claude/         Claude Agent SDK project memory (skills, agents, settings)
ARCHITECTURE.md  System design and request lifecycle (this repo, not loaded at runtime)
README.md        You are here
configs/         YAML business configuration (action/bonus/schedule/operator catalogs)
data/
  kpis.csv       The single global KPI catalog (1,277 rows)
  sdk_context/   Development reference material (NOT read at runtime)
app/             Python package (FastAPI, orchestrator, MCP tools, services)
tests/           Unit, integration, golden, smoke
logs/            Runtime artifacts (audit logs, persisted rules)
scripts/         Dev + run helpers (setup_dev.py, run_api.py)
```

---

## Quickstart

```bash
python scripts/setup_dev.py
.venv/Scripts/activate
python scripts/run_api.py
```

Then:

```bash
curl -X POST http://127.0.0.1:8000/rule/build \
  -H "Content-Type: application/json" \
  -d '{"client":"omantel","sentence":"Send a promotional SMS to prepaid users who recharged more than 50 OMR last month."}'
```

Successful response (truncated):

```json
{
  "ok": true,
  "request_id": "req-abc",
  "intermediate_rule": "# client: omantel\nif ( CUST_360_RECHARGE_MTD > \"50\" ) {\n  action(ActionName=\"Send Promotion\", CHANNEL=\"SMS\", PRODUCT_ID=\"\", MESSAGE=\"Recharge bonus offer\")\n}\nschedule(schedule_type=\"ScheduleNow\", repeat=\"No\", segment_rule_start_date=\"\", segment_rule_end_date=\"\", select_days=\"\")",
  "final_rule_json": null,
  "validation_verdict": null,
  "user_message": null,
  "warnings": [],
  "errors": []
}
```

Every `kpi` in the rendered if-block is a real entry from `data/kpis.csv`
(either a `column_name` or a `feature_name`). The validator rejects any
fabricated column name.

---

## The pipeline (six stages)

| Stage | Who | What |
|---|---|---|
| 1. **Validate** | Claude reasoning + `extract_segment_markers` | Decide: `proceed` / `decompose` / `clarify` |
| 2. **Components** | Claude reasoning + lookup tools | Resolve condition, action, bonus (+benefit), schedule (one per statement) |
| 3. **Compose** | Claude reasoning + `render_intermediate_rule` | Write the if-block string per `intermediate-rule.md` |
| 4. **Technical validate** | Python, deterministic | Placeholder discipline, operator legality, **catalog provenance** |
| 5. **Parse to final JSON** | Python, deterministic (port from `final_rule_json`) | if-block → `id/pid/childrens` tree the campaign engine consumes |
| 6. **User message** | Claude reasoning, ~300-400 tokens | Plain-English summary of the emitted rule |

The verifier subagent (`runer.md`) runs in its own context per
`RULE_VERIFIER_MODE` (`none` / `per-step` / `end-only`). Default: `none`
(declared, not yet invoked).

> Stages 5 and 6 are **not yet wired** into the orchestrator's MCP tool
> surface. The Python modules (`parse_intermediate_to_final.py`,
> `build_user_message`) exist; the orchestrator currently stops after Stage 4.

---

## Configuration

YAML catalogs in `configs/`:

| File | Purpose |
|---|---|
| `action_catalog.yaml` | action types (data_bonus, send_promotion, etc.) |
| `bonus_catalog.yaml` | bonus types and aggregations |
| `schedule_catalog.yaml` | 9 schedule types |
| `operator_catalog.yaml` | operators and their valid data types |
| `policy_catalog.yaml` | eligibility, exclusions, conflicts (not yet implemented) |
| `clients.yaml` | multi-tenant config (currently single-tenant at runtime) |
| `common_prompts.yaml` | shared prompt fragments |

Environment variables (secrets and runtime settings):

```
ANTHROPIC_BASE_URL=http://localhost:11434      # Ollama endpoint (SDK reads natively)
ANTHROPIC_API_KEY=ollama                       # placeholder (SDK reads natively)
RULE_ORCHESTRATOR_MODEL=claude-sonnet-4.5
RULE_SUBAGENT_MODEL=claude-haiku-4.5
RULE_MAX_TURNS=25
RULE_VERIFIER_MODE=none                        # none | per-step | end-only
RULE_REQUEST_TIMEOUT=90                        # seconds; hard cap per request
RULE_DEBUG=0                                   # 1 to dump assistant text + per-tool payloads
DB_HOST=10.0.10.24
DB_NAME=Magik_3.0_Demo_Upgrade
DB_USER=magikuser
DB_PASSWORD=<set at deploy>
```

---

## Tests

```bash
pytest                                           # all unit + integration
pytest tests/unit                                # unit only (fast)
pytest -m smoke                                  # live SDK tests (needs ANTHROPIC_API_KEY)
```

---

## Key invariants

1. KPI CSV (`data/kpis.csv`) is the single source of truth for KPIs.
2. YAML catalogs hold business configuration only; no secrets.
3. Environment variables hold secrets + runtime settings only; no business config.
4. `parse_intermediate_to_final` follows the regex/parse logic from `data/sdk_context/final_rule_json` as-is.
5. Intermediate rule contract: `.claude/skills/parser/references/intermediate-rule.md`.
6. Final JSON contract: `.claude/skills/parser/references/final-rule-json.md`.
7. One schedule per statement. Multiple branches (if/else-if) share one schedule.
8. Bonus criteria attach to an action (per-branch); bonus = `BONUS_CRITERIA` inside the action block.
9. `ActionName` is "Send Promotion" this round. "Send Bonus" is reserved.
10. `data/sdk_context/` is dev reference only. Runtime never reads it.
11. **Every emitted `kpi` must be catalog-proven** — the validator rejects any
    KPI that is neither in `data/kpis.csv` nor in the `approved_kpis` set
    populated by `retrieve_kpis` for this request.

---

## What's done in this build

- **Phase 0**: Two contract docs (`intermediate-rule.md`, `final-rule-json.md`); removed wrong validation code
- **Phase 1**: Schemas (Benefit, BonusCriteria, ActionBlock, ScheduleBlock, RuleCandidate, RuleState, RuleBuildRequest/Response); `catalog_lookup.py` over `configs/*.yaml`
- **Phase 2**: `extract_segment_markers` evidence tool; rewrote all 8 skill MDs (validation, condition, action, bonus, schedule, parser, message, policy-stub)
- **Phase 3**: Stage 2 lookup tools (`lookup_action`, `lookup_bonus`, `lookup_schedule`, `lookup_policy` DEFERRED)
- **Phase 4**: Real `pyodbc` connection in `sql_lookup._connect()`; 4 SQL functions (product, profile, action, bonus details) query live DB; env-var credentials
- **Phase 5**: `render_intermediate_rule` (Python emits the if-block) and `validate_intermediate_rule` (placeholder + operator + column checks)
- **Phase 6**: `parse_intermediate_to_final` — full port from `data/sdk_context/final_rule_json`, including PascalCase field mapping and ISO→DD/MM/YYYY date conversion
- **Phase 7**: Orchestrator wiring (`ORCHESTRATOR_APPEND`); `_run_agentic` in `app/api.py` drives Claude SDK session end-to-end
- **Phase 8**: `build_user_message` Python fallback (templated 300-400 token summary walking the final JSON)
- **Phase 9**: Real BM25 + char-ngram hybrid `retrieve_kpis` over `data/kpis.csv` (1,277 rows), with paged expansion and unresolved-role detection
- **Phase 10**: Verifier subagent runs in its own SDK context per `RULE_VERIFIER_MODE` (default `none`)
- **Phase 11 (post-fix)**: Validator enforces catalog provenance — every emitted `kpi` must trace back to `kpis.csv` or to a `retrieve_kpis` result captured for this request. Tool result shape is now tolerant of the model wrapping single predicates in `{"item": ...}`. `retrieve_kpis` applies a `min_score` quality gate. Full details in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## How to run with Ollama

```bash
# Install pyodbc + the ODBC driver for your SQL Server
.venv/Scripts/python.exe -m pip install pyodbc

# Set env vars (Ollama + DB + optional Langfuse)
export ANTHROPIC_BASE_URL=https://your-ollama-url
export ANTHROPIC_API_KEY=ollama
export RULE_ORCHESTRATOR_MODEL=minimax-m3:cloud
export RULE_SUBAGENT_MODEL=minimax-m3:cloud
export DB_HOST=10.0.10.24
export DB_NAME=Magik_3.0_Demo_Upgrade
export DB_USER=magikuser
export DB_PASSWORD=<set at deploy>

# Start the server
.venv/Scripts/python.exe scripts/run_api.py

# Send a request
curl -X POST http://127.0.0.1:8000/rule/build \
  -H "Content-Type: application/json" \
  -d '{"client":"omantel","sentence":"Send a promotional SMS to prepaid users who recharged more than 50 OMR last month."}'
```

The pipeline runs all six stages. Claude reasons about validation,
components, and the if-block composition. Python emits the canonical if-block
string, validates it against the operator catalog and KPI catalog (with
catalog-provenance enforcement), parses to the final `id/pid/childrens` tree
with DB lookups for `profile_id`, `action_id`, `product_id`, and bonus
details. The user message (300-400 tokens) walks the tree and summarizes the
emitted rule.

---

## What's NOT in this round

- `policy` skill implementation (deferred per `data/sdk_context/base_info`).
- Multi-tenant per-client files in `data/sdk_context/catalogs/` and `policies/`.
- Per-step verifier invocation (currently `end-only` is wired; `per-step` is a future round).
- Sentence-transformers backend (currently char-ngram only; switch via `RULE_EMBEDDING_BACKEND=sentence-transformers` once installed).
- **Subagent wiring**: `builder.md` and `verifier.md` are defined in `.claude/agents/` but `build_agents(...)` in the orchestrator returns `{}`. Stages 5 and 6 of the pipeline (parse to final JSON, build user message) are not yet invoked by the orchestrator. The Python modules exist.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md), `.claude/CLAUDE.md`,
`.claude/skills/*/SKILL.md`, and
`.claude/skills/parser/references/*.md` for the contracts and procedures.