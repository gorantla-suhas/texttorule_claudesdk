"""Slot normalization — deterministic first-pass parse.

Maps a raw marketer sentence into a small, structured slot envelope.
The orchestrator reads this as evidence, then corrects and completes
the slots semantically.
"""

from __future__ import annotations

from typing import Any


def normalize_slots(request: str, client: str | None = None) -> dict[str, Any]:
    """Parse common phrases into a slots envelope.

    TODO: port the deterministic patterns from
    `vp_agent/tools/normalize.py`. For now returns an empty envelope
    so the surface is stable.
    """

    return {
        "client": client,
        "request": request,
        "slots": {
            "intent": None,
            "action": None,
            "metric": None,
            "filters": [],
            "time_window": None,
        },
    }
