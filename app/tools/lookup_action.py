"""Action catalog lookup — Stage 2b MCP tool implementation.

Reads `configs/action_catalog.yaml` and returns candidates matching
the user's action phrase. Pure Python, deterministic, no I/O.
"""

from __future__ import annotations

from typing import Any

from app.services import catalog_lookup


def lookup_action(phrase: str, client: str) -> dict[str, Any]:
    """Return action candidates matching the phrase.

    Output shape (per the MCP contract):

        {
          "actions": [
            {
              "type": "send_sms",
              "category": "communication",
              "product_family": null,
              "required_params": ["template_id"],
              "optional_params": [],
              "default_params": {}
            },
            ...
          ],
          "match_count": <int>
        }

    If no candidates match, returns `{"actions": [], "match_count": 0}`.
    Claude reasons over an empty list (typically → clarification).
    """

    if not phrase or not phrase.strip():
        return {"actions": [], "match_count": 0}

    candidates = catalog_lookup.search_actions_by_phrase(phrase)

    # Sort: exact type match first, then by token overlap (rough heuristic).
    target = phrase.strip().lower()
    scored = []
    for entry in candidates:
        type_str = str(entry.get("type", "")).lower()
        score = 0
        if type_str == target:
            score += 100
        elif target in type_str or type_str in target:
            score += 50
        # +1 per token overlap (already filtered by search)
        scored.append((score, entry))
    scored.sort(key=lambda x: x[0], reverse=True)

    out = []
    for _score, entry in scored:
        out.append({
            "type": entry.get("type"),
            "category": entry.get("category"),
            "product_family": entry.get("product_family"),
            "required_params": list(entry.get("required_params", []) or []),
            "optional_params": list(entry.get("optional_params", []) or []),
            "default_params": dict(entry.get("default_params", {}) or {}),
        })

    return {"actions": out, "match_count": len(out)}


def get_required_params(action_type: str) -> list[str]:
    """Convenience for the action skill: return required param names."""

    entry = catalog_lookup.find_action_by_type(action_type)
    if not entry:
        return []
    return list(entry.get("required_params", []) or [])


def get_default_params(action_type: str) -> dict[str, Any]:
    """Convenience for the action skill: return default param values."""

    entry = catalog_lookup.find_action_by_type(action_type)
    if not entry:
        return {}
    return dict(entry.get("default_params", {}) or {})


__all__ = ["lookup_action", "get_required_params", "get_default_params"]