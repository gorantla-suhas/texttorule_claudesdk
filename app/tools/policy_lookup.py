"""Policy catalog lookup.

Combines the base catalog (`configs/policy_catalog.yaml`) with the
client-specific overrides (`data/sdk_context/policies/<client>_policies.json`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PolicyDecision:
    """Result of a policy lookup."""

    conflicts: list[str]
    eligibility: dict[str, Any]
    exclusions: list[dict[str, Any]]


def lookup_policy(
    client: str,
    audience: dict[str, Any] | None = None,
    bonus_type: str | None = None,
) -> PolicyDecision:
    """Resolve eligibility, exclusions, and conflicts for a request.

    TODO: implement against the base catalog + client overrides.
    """

    return PolicyDecision(conflicts=[], eligibility={}, exclusions=[])
