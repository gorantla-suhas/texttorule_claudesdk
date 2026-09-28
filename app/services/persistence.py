"""Persistence helpers.

Per-request audit logs and emitted rules are persisted to
`logs/audit_<id>.json` and `logs/rule_<id>.json` respectively (or
the directory pointed to by `RULE_AUDIT_DIR`). These are the only
side effects outside of the KPI catalog.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.config import load_settings


def _audit_path(trace_id: str) -> Path:
    audit_dir = load_settings().audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir / f"audit_{trace_id}.json"


def append_audit_record(trace_id: str, record: dict[str, Any]) -> None:
    """Append one audit record to the trace's audit file."""

    path = _audit_path(trace_id)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"trace_id": trace_id, "records": []}
    data["records"].append(record)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_audit_log(trace_id: str) -> list[dict[str, Any]]:
    """Load the full audit log for a trace id."""

    path = _audit_path(trace_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("records", [])


def save_rule(rule: dict[str, Any]) -> str:
    """Persist a Rule JSON and return its id."""

    audit_dir = load_settings().audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    rule_id = f"rule-{uuid.uuid4().hex[:12]}"
    path = audit_dir / f"{rule_id}.json"
    path.write_text(json.dumps(rule, indent=2, default=str), encoding="utf-8")
    return rule_id
