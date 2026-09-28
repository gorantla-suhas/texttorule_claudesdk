"""texttorule_engine — telecom rule engine.

A Claude SDK centric system that converts natural-language campaign
rules into structured Rule JSON. Python owns deterministic execution
and infrastructure; the Claude Agent SDK orchestrator owns reasoning,
skill selection, and decision making.

Entry points:

- `app.server` — FastAPI app factory.
- `app.cli` — `rule-engine` command-line entry point.
- `app.orchestrator` — Claude Agent SDK session driver.
- `app.tools` — in-process MCP server exposing the rule tools.
"""

__version__ = "0.1.0"
