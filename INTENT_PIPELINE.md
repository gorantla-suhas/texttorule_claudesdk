# Primary path: Claude Agent SDK session

The runtime uses the Claude Agent SDK session in
`app/orchestrator.py`. The HTTP endpoint `POST /rule/build`
calls `_run_agentic` in `app/api.py`, which streams one
`ClaudeSDKClient` session per request. The orchestrator drives a
6-stage tool loop, calling the MCP tools exposed in
`app/tools/__init__.py` (render, validate, parse, lookup_*).

The helper modules `app/services/intent_decomposer.py` and
`app/services/intent_models.py` are kept as a typed-decomposition
utility but are not wired into the runtime path.
