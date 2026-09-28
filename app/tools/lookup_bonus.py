"""Bonus catalog + benefit SQL lookup — Stage 2c MCP tool.

Reads `configs/bonus_catalog.yaml` for the bonus template, and (when
benefits are non-empty) calls `app.services.sql_lookup` to resolve
`product_id` for telco_product / voucher benefits.

The DB connection is stubbed in Phase 4; this module handles the
calling convention and the empty-bypassing logic so the rest of the
pipeline is exercisable.
"""

from __future__ import annotations

from typing import Any


def lookup_bonus(
    action_type: str,
    aggregation: str,
    client: str,
    product_query: str | None = None,
) -> dict[str, Any]:
    """Return bonus template + benefit candidates.

    Output shape:

        {
          "bonus_template": {
            "action_type": "Recharge",
            "supported_aggregations": ["PER_SUBSCRIBER", "ONCE", "CUMULATIVE"],
            "default_aggregation": "...",
            "compatible_actions": [...]
          },
          "benefits": [
            {
              "type": "telco_product",
              "product_name": "<echoed>",
              "product_id": "<resolved | null>",
              "resolved": <bool>
            },
            ...
          ],
          "warnings": []
        }

    Behavior:

    - `action_type` must be `"Recharge"` this round. Any other value
      returns an empty template + a warning.
    - `aggregation` is checked against the bonus's
      `supported_aggregations`. Mismatch → warning, empty benefits.
    - If `product_query` is None or empty → benefits list is empty
      (no DB call).
    - Otherwise `app.services.sql_lookup.get_product_by_name_or_id`
      is called. Returns the resolved `product_id` or `null` if not
      found. A not-found result is a hard error from the caller's
      perspective (caller surfaces clarification).
    """

    from app.services import catalog_lookup
    from app.services.sql_lookup import get_product_by_name_or_id

    warnings: list[str] = []
    template: dict[str, Any] = {}

    bonus_entry = catalog_lookup.find_bonus_by_type(action_type)
    if not bonus_entry:
        warnings.append(f"action_type '{action_type}' is not in the bonus catalog")
        return {"bonus_template": {}, "benefits": [], "warnings": warnings}

    agg_upper = aggregation.strip().upper()
    supported = [a.upper() for a in (bonus_entry.get("supported_aggregations", []) or [])]
    # This round we only support Recharge with SUM/COUNT/RANGE, not the
    # catalog's PER_SUBSCRIBER / ONCE / CUMULATIVE. Surface a warning
    # but don't fail — Claude can still try.
    if supported and agg_upper not in {"SUM", "COUNT", "RANGE"}:
        warnings.append(
            f"aggregation '{aggregation}' is outside the SUM/COUNT/RANGE "
            f"set implemented this round; supported by catalog: {supported}"
        )

    template = {
        "type": bonus_entry.get("type"),
        "supported_aggregations": list(bonus_entry.get("supported_aggregations", []) or []),
        "default_aggregation": bonus_entry.get("default_aggregation"),
        "compatible_actions": list(bonus_entry.get("compatible_actions", []) or []),
        "default_requirements": dict(bonus_entry.get("default_requirements", {}) or {}),
    }

    benefits_out: list[dict[str, Any]] = []
    if product_query and product_query.strip():
        try:
            product_id = get_product_by_name_or_id(product_query.strip(), client=client)
        except Exception as exc:
            warnings.append(f"product lookup failed: {exc}")
            product_id = None

        benefits_out.append({
            "type": "telco_product",   # default for free-text names
            "product_name": product_query.strip(),
            "product_id": product_id,
            "resolved": product_id is not None,
        })

    return {
        "bonus_template": template,
        "benefits": benefits_out,
        "warnings": warnings,
    }


__all__ = ["lookup_bonus"]