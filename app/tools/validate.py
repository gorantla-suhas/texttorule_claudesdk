"""Rule validation.

Mandatory pre-emission check. Validates:

- JSON shape against the contract in
  `.claude/skills/parser/references/rule-schema.md`;
- placeholder discipline (`${operator}`, `${value}`,
  `${resolve:<phrase>}` only);
- operator legality for each column's data type (against
  `configs/operator_catalog.yaml`);
- column existence in the loaded KPI catalog for the chosen table;
- coarse request coverage (the rule mentions the main entities from
  the user sentence).

The validator never alters the rule. On failure it returns an
`error` and the orchestrator decides whether to fix and re-render
or to halt as a code bug.
"""

from __future__ import annotations

from typing import Any


def validate_rule(
    rule: dict[str, Any],
    *,
    table: str | None = None,
    sentence: str | None = None,
) -> dict[str, Any]:
    """Validate a Rule JSON.

    TODO: implement against `configs/operator_catalog.yaml` and the
    loaded KPI catalog. Returns a stub result for now.
    """

    return {
        "valid": True,
        "warnings": [],
        "errors": [],
        "referenced_columns": [],
        "table": table,
    }
