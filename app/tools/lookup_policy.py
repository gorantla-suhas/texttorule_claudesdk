"""Policy lookup — DEFERRED.

Per `data/sdk_context/base_info` section 6, policy implementation is
deferred. This module returns the empty shape so the rest of the
pipeline is exercisable.
"""

from __future__ import annotations

from typing import Any


def lookup_policy(client: str, audience: dict[str, Any] | None = None,
                  bonus_type: str | None = None) -> dict[str, Any]:
    """Return an empty policy result (DEFERRED).

    When implemented, this will read `configs/policy_catalog.yaml`,
    filter by `client_scope`, and detect conflicts with the given
    audience + bonus combination.
    """

    return {
        "conflicts": [],
        "eligibility": {},
        "exclusions": [],
        "warnings": ["policy skill is deferred this round"],
    }


__all__ = ["lookup_policy"]