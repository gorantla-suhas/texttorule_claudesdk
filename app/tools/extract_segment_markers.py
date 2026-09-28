"""Segment marker extraction — Stage 1 evidence helper.

Returns candidate split points in a marketer sentence for the
decompose verdict. Pure Python, deterministic, no I/O.

Claude (the validation skill) reads the marker list and decides
whether the sentence splits into N sub-rules or stays as one.

The markers are EVIDENCE, not decisions. Claude still reasons from
the full sentence context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


MarkerKind = Literal["split", "weak"]


@dataclass
class SegmentMarker:
    """One candidate split point."""

    position: int          # character offset in the input string
    marker: str            # the matched phrase (lowercased)
    kind: MarkerKind       # "split" = strong signal, "weak" = contextual
    raw: str               # the original-case span from the input

    def to_dict(self) -> dict:
        return {
            "position": self.position,
            "marker": self.marker,
            "kind": self.kind,
            "raw": self.raw,
        }


# Strong markers — these almost always mean "new sub-rule".
_STRONG_MARKER_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\botherwise,?\s+if\b",        "otherwise if"),
    (r"\botherwise\b",               "otherwise"),
    (r"\belse\s+if\b",               "else if"),
    (r"\belse\b",                    "else"),
    (r"\bin\s+case\b",               "in case"),
    (r"\bfor\s+the\s+rest\b",        "for the rest"),
    (r"\bfor\s+other\s+users?\b",    "for other users"),
    (r"\bfor\s+inactive\s+users?\b", "for inactive users"),
    (r"\bfor\s+active\s+users?\b",   "for active users"),
    (r"\bif\s+not\b.*?\bthen\b",     "if not ... then"),
)


# Weak markers — contextually may or may not indicate a split.
# "weak" markers inside a single-targeting clause are noise; only
# matter when paired with another audience/condition.
_WEAK_MARKER_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(?:and|then)\s+for\s+the\s+(?:other|remaining)\b", "and for the other/remaining"),
    (r"\b(?:and|then)\s+for\s+(?:the\s+)?inactive\b",         "and for inactive"),
    (r"\b(?:and|then)\s+for\s+(?:the\s+)?active\b",            "and for active"),
)


def extract_segment_markers(sentence: str) -> list[dict]:
    """Return a list of marker dicts in the order they appear in `sentence`.

    Output shape (per marker):
        {
          "position": int,       # character offset
          "marker":   str,       # normalized lowercase marker text
          "kind":     "split" | "weak",
          "raw":      str,       # original-case text from the input
        }

    The list is empty when no candidate splits are found.
    """

    if not sentence:
        return []

    markers: list[SegmentMarker] = []
    seen_positions: set[int] = set()

    for pattern, label in _STRONG_MARKER_PATTERNS:
        for m in re.finditer(pattern, sentence.lower()):
            pos = m.start()
            if pos in seen_positions:
                continue
            seen_positions.add(pos)
            raw = sentence[m.start(): m.end()]
            markers.append(SegmentMarker(position=pos, marker=label, kind="split", raw=raw))

    for pattern, label in _WEAK_MARKER_PATTERNS:
        for m in re.finditer(pattern, sentence.lower()):
            pos = m.start()
            if pos in seen_positions:
                continue
            seen_positions.add(pos)
            raw = sentence[m.start(): m.end()]
            markers.append(SegmentMarker(position=pos, marker=label, kind="weak", raw=raw))

    markers.sort(key=lambda x: x.position)
    return [m.to_dict() for m in markers]


def has_strong_marker(markers: list[dict]) -> bool:
    """Convenience: True when at least one strong-split marker is present."""

    return any(m.get("kind") == "split" for m in markers)


def count_strong_markers(markers: list[dict]) -> int:
    """Convenience: number of strong-split markers."""

    return sum(1 for m in markers if m.get("kind") == "split")


__all__ = ["extract_segment_markers", "has_strong_marker", "count_strong_markers"]