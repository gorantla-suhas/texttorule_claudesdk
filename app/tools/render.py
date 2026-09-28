"""Rule JSON renderer — the only legal emitter.

The renderer turns a template string + variables + filters into the
final Rule JSON. It enforces:

- the placeholders are exactly `${operator}`, `${value}`, and
  `${resolve:<phrase>}`;
- the column names referenced in the template exist in the loaded
  KPI catalog for the chosen table;
- the JSON is parseable.

The renderer is **not** a semantic checker. `validate_rule` is
called separately and owns grammar/coverage.
"""

from __future__ import annotations

import json
import re
from typing import Any


PLACEHOLDER_RE = re.compile(r"\$\{(?:operator|value|resolve:[a-zA-Z0-9_]+)\}")


def render_rule(
    *,
    template: str,
    variables: dict[str, Any],
    filters: list[dict[str, Any]],
    client: str,
) -> dict[str, Any]:
    """Render the Rule JSON.

    TODO: implement the actual template substitution, JSON composition,
    and placeholder discipline check. Returns a dict for now.
    """

    return {
        "client": client,
        "template": template,
        "variables": variables,
        "filters": filters,
    }


def find_placeholders(text: str) -> set[str]:
    """Return the set of `${...}` placeholders present in `text`."""

    return set(PLACEHOLDER_RE.findall(text))
