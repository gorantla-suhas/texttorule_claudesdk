"""Catalog lookups (deterministic, no I/O at request time).

Reads `configs/*.yaml` once per process via `app.tools.config_loader`
and exposes typed-ish accessor functions used by the lookup MCP
tools (`lookup_action`, `lookup_bonus`, `lookup_schedule`,
`lookup_policy`).

This module does NOT:
- Make business decisions (which action fits, which bonus to use)
- Call the LLM
- Read `data/sdk_context/` (those are dev reference only)
- Connect to the database (DB lookups live in `app.services.sql_lookup`)

The MCP tools read these functions to give Claude evidence; Claude
still picks the right answer.
"""

from __future__ import annotations

from typing import Any

from app.tools.config_loader import load_config


# ---------------------------------------------------------------------------
# Action catalog
# ---------------------------------------------------------------------------


def list_actions() -> list[dict[str, Any]]:
    """Return all action entries from `action_catalog.yaml`."""

    cfg = load_config("action_catalog")
    return list(cfg.get("actions", []))


def find_action_by_type(action_type: str) -> dict[str, Any] | None:
    """Return the action entry whose `type` matches `action_type`.

    `action_type` is the canonical key (e.g. "data_bonus",
    "send_promotion"). Match is case-insensitive.
    """

    target = action_type.strip().lower()
    for entry in list_actions():
        if str(entry.get("type", "")).lower() == target:
            return entry
    return None


def search_actions_by_phrase(phrase: str) -> list[dict[str, Any]]:
    """Return actions whose type/category contain any token of `phrase`.

    Lightweight evidence helper. Claude reasons over the candidates.
    """

    tokens = [t for t in phrase.lower().split() if len(t) > 2]
    if not tokens:
        return []
    out: list[dict[str, Any]] = []
    for entry in list_actions():
        haystack = " ".join([
            str(entry.get("type", "")),
            str(entry.get("category", "")),
            " ".join(entry.get("required_params", []) or []),
            " ".join(entry.get("optional_params", []) or []),
        ]).lower()
        if any(tok in haystack for tok in tokens):
            out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Bonus catalog
# ---------------------------------------------------------------------------


def list_bonuses() -> list[dict[str, Any]]:
    """Return all bonus entries from `bonus_catalog.yaml`."""

    cfg = load_config("bonus_catalog")
    return list(cfg.get("bonuses", []))


def find_bonus_by_type(bonus_type: str) -> dict[str, Any] | None:
    """Return the bonus entry whose `type` matches `bonus_type`."""

    target = bonus_type.strip().lower()
    for entry in list_bonuses():
        if str(entry.get("type", "")).lower() == target:
            return entry
    return None


def compatible_actions_for_bonus(bonus_type: str) -> list[str]:
    """Return the list of action types compatible with `bonus_type`."""

    entry = find_bonus_by_type(bonus_type)
    if not entry:
        return []
    return list(entry.get("compatible_actions", []) or [])


def supported_aggregations(bonus_type: str) -> list[str]:
    """Return the SQL aggregation functions supported by `bonus_type`."""

    entry = find_bonus_by_type(bonus_type)
    if not entry:
        return []
    return [a.upper() for a in (entry.get("supported_aggregations", []) or [])]


# ---------------------------------------------------------------------------
# Schedule catalog
# ---------------------------------------------------------------------------


def list_schedule_types() -> list[dict[str, Any]]:
    """Return all schedule entries from `schedule_catalog.yaml`."""

    cfg = load_config("schedule_catalog")
    return list(cfg.get("schedules", []))


def find_schedule_type(schedule_type: str) -> dict[str, Any] | None:
    """Return the schedule entry whose `type` matches `schedule_type`."""

    target = schedule_type.strip().lower()
    for entry in list_schedule_types():
        if str(entry.get("type", "")).lower() == target:
            return entry
    return None


# ---------------------------------------------------------------------------
# Operator catalog
# ---------------------------------------------------------------------------


def list_operators() -> list[dict[str, Any]]:
    """Return all operator entries from `operator_catalog.yaml`."""

    cfg = load_config("operator_catalog")
    return list(cfg.get("operators", []))


def find_operator(op: str) -> dict[str, Any] | None:
    """Return the operator entry whose `op` matches `op`.

    Match is case-insensitive and tolerant of `<>` vs `!=`.
    """

    target = op.strip().lower()
    aliases = {"<>": "!=", "!=": "!="}
    target = aliases.get(target, target)
    for entry in list_operators():
        if str(entry.get("op", "")).lower() == target:
            return entry
    return None


def operator_valid_for_data_type(op: str, data_type: str) -> bool:
    """Return True if `op` is legal for columns with `data_type`.

    `data_type` ∈ {"numeric", "string", "categorical", "date"} per
    `data/kpis.csv`. The operator catalog declares `valid_for: [...]`.
    """

    entry = find_operator(op)
    if not entry:
        return False
    valid_for = [str(d).lower() for d in (entry.get("valid_for", []) or [])]
    return data_type.strip().lower() in valid_for


# ---------------------------------------------------------------------------
# Policy catalog (DEFERRED — read-only for now)
# ---------------------------------------------------------------------------


def list_policies(client: str | None = None) -> list[dict[str, Any]]:
    """Return policy entries from `policy_catalog.yaml`.

    Optionally filtered to those whose `client_scope` contains
    `client`. Returns all if `client` is None.
    """

    cfg = load_config("policy_catalog")
    entries = list(cfg.get("policies", []))
    if client is None:
        return entries
    out = [
        e for e in entries
        if not e.get("client_scope") or client in e.get("client_scope", [])
    ]
    return out


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


def get_client_config(client: str) -> dict[str, Any] | None:
    """Return the per-tenant config for `client` from `clients.yaml`."""

    cfg = load_config("clients")
    return cfg.get("clients", {}).get(client)


__all__ = [
    "list_actions",
    "find_action_by_type",
    "search_actions_by_phrase",
    "list_bonuses",
    "find_bonus_by_type",
    "compatible_actions_for_bonus",
    "supported_aggregations",
    "list_schedule_types",
    "find_schedule_type",
    "list_operators",
    "find_operator",
    "operator_valid_for_data_type",
    "list_policies",
    "get_client_config",
]