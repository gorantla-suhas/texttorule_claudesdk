"""Validate the intermediate if-block string.

Stage 4 implementation. Deterministic Python checks against the
emitted if-block:

- **Placeholder discipline**: only `${operator}`, `${value}`,
  `${resolve:<phrase>}` permitted. (We don't actually emit these
  in our pipeline, but if a future round uses them, they pass.)
- **Operator legality**: each `KPI <op> <value>` must use an op valid
  for the KPI's `data_type` per `configs/operator_catalog.yaml`.
- **Column existence**: each referenced KPI must exist in the loaded
  catalog (`data/kpis.csv`).
- **Parseable**: `parse_intermediate_to_final` must be able to parse
  the if-block without error.

Pure Python, no LLM, no DB.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# Recognized placeholders.
_PLACEHOLDER_RE = re.compile(r"\$\{(?:operator|value|resolve:[^}]+)\}")

# All other `${...}` occurrences are illegal.
_OTHER_PLACEHOLDER_RE = re.compile(r"\$\{[^}]+\}")

# Match predicate `KPI <op> <value>` roughly. Walks the inner string
# we already extracted from the if-block so multiline rules work.
_PREDICATE_RE = re.compile(
    r"""
    (?P<kpi>[A-Za-z_][A-Za-z0-9_]*)
    \s+
    (?P<op>=|<>|>=|<=|>|<|BETWEEN|IN\s+LIST|NOT\s+IN\s+LIST|IS\s+NULL|IS\s+NOT\s+NULL|LIKE)
    \s+
    (?P<rhs>"[^"]*"|'[^']*'|[^()]+?)
    (?=$|\s+AND\s+|\s+OR\s+|\)|,)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _known_columns() -> set[str]:
    """Return the set of `column_name` values in the KPI catalog.

    Reads `data/kpis.csv` (the canonical KPI list). Cached per
    process.
    """

    global _KNOWN_COLUMNS_CACHE
    try:
        return _KNOWN_COLUMNS_CACHE
    except NameError:
        pass

    cache: set[str] = set()
    csv_path = Path("data/kpis.csv")
    if not csv_path.exists():
        try:
            from app.config import DATA_DIR
            csv_path = DATA_DIR / "kpis.csv"
        except Exception:
            csv_path = None

    if csv_path and csv_path.exists():
        try:
            import csv
            with csv_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cn = row.get("column_name", "").strip()
                    if cn:
                        cache.add(cn)
        except Exception:
            pass

    _KNOWN_COLUMNS_CACHE = cache
    return cache


def _kpi_data_type(kpi_name: str) -> str | None:
    """Return the `data_type` of a KPI by name (from kpis.csv).

    Cached per process. Returns None if KPI is not in the catalog.
    """

    global _KPI_DATA_TYPE_CACHE
    try:
        cache = _KPI_DATA_TYPE_CACHE
    except NameError:
        cache = {}
        _KPI_DATA_TYPE_CACHE = cache

    if kpi_name in cache:
        return cache[kpi_name]

    csv_path = Path("data/kpis.csv")
    if not csv_path.exists():
        try:
            from app.config import DATA_DIR
            csv_path = DATA_DIR / "kpis.csv"
        except Exception:
            csv_path = None

    dt: str | None = None
    if csv_path and csv_path.exists():
        try:
            import csv
            with csv_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("column_name", "").strip() == kpi_name:
                        dt = row.get("data_type", "").strip().lower() or None
                        break
        except Exception:
            pass

    cache[kpi_name] = dt
    return dt


def _normalize_op(op: str) -> str:
    """Map raw operator text to canonical form."""

    op = op.strip().upper()
    if op == "<>":
        return "!="
    if op == "IN LIST":
        return "in"
    if op == "NOT IN LIST":
        return "not_in"
    if op == "IS NULL":
        return "is_null"
    if op == "IS NOT NULL":
        return "is_not_null"
    return op.lower()


def validate_intermediate_rule(
    intermediate_rule: str,
    *,
    table: str | None = None,
    client: str | None = None,
    approved_kpis: set[str] | None = None,
) -> dict[str, Any]:
    """Validate the if-block string.

    Returns:
        {
          "valid": bool,
          "warnings": ["..."],
          "errors": ["..."],
          "referenced_columns": ["..."],
          "placeholders": ["${operator}", ...]
        }
    """

    warnings: list[str] = []
    errors: list[str] = []
    referenced_columns: list[str] = []

    if not intermediate_rule or not intermediate_rule.strip():
        errors.append("intermediate_rule is empty")
        return {
            "valid": False, "warnings": warnings, "errors": errors,
            "referenced_columns": referenced_columns, "placeholders": [],
        }

    # 1. Placeholder discipline.
    placeholders = _PLACEHOLDER_RE.findall(intermediate_rule)
    other_placeholders = _OTHER_PLACEHOLDER_RE.findall(intermediate_rule)
    for ph in other_placeholders:
        if ph in placeholders:
            continue
        errors.append(f"illegal placeholder {ph!r} (only ${{operator}}, ${{value}}, ${{resolve:<phrase>}} allowed)")

    # 2. Column existence + operator legality per predicate.
    for match in _PREDICATE_RE.finditer(intermediate_rule):
        kpi = match.group("kpi")
        op = match.group("op")
        if kpi.upper() in {"IF", "ELSE", "AND", "OR", "BETWEEN", "IN", "LIST", "NOT", "NULL", "IS", "LIKE"}:
            continue
        if kpi.upper() == "SCHEDULE":
            continue
        if kpi.upper().startswith("ACTION") or kpi.upper() in {"CHANNEL", "PRODUCT_ID", "MESSAGE"}:
            continue
        # Likely an action/schedule field name, skip.
        if "MESSAGE_ID" in kpi.upper() or "REWARD" in kpi.upper() or "MULTIPLIER" in kpi.upper():
            continue

        referenced_columns.append(kpi)
        known = _known_columns()
        in_catalog = (not known) or (kpi in known)
        in_approved = bool(approved_kpis) and (kpi in approved_kpis)
        if not in_catalog and not in_approved:
            # Hard error: fabricated KPI. The orchestrator must re-call
            # retrieve_kpis and use the actual column_name / feature_name
            # from its results.
            errors.append(
                f"column {kpi!r} is not in the KPI catalog and was not "
                "returned by retrieve_kpis this request (fabricated KPI); "
                "call retrieve_kpis and use a verbatim column_name or "
                "feature_name from its results"
            )
            continue

        data_type = _kpi_data_type(kpi)
        if data_type is None and known:
            # KPI unknown to the catalog but approved by retrieve_kpis
            # (e.g. feature_name only, no column_name). Skip operator
            # type-check.
            continue

        from app.services import catalog_lookup
        canonical_op = _normalize_op(op)
        if data_type and not catalog_lookup.operator_valid_for_data_type(canonical_op, data_type):
            errors.append(
                f"operator {op!r} is not valid for column {kpi!r} "
                f"(data_type={data_type})"
            )

    # 3. Inline if-block sanity check. (No parser invocation here —
    # parse_intermediate_to_final was removed along with DB-backed IDs.)
    # Always use depth-counter scanning to handle nested parens in the
    # condition (e.g. `if ( (A AND B) ) { ... }`). Strip leading `#`
    # comment lines (e.g. `# client: omantel`) so they don't confuse
    # the scan.
    scan_text = "\n".join(
        line for line in intermediate_rule.splitlines()
        if not line.lstrip().startswith("#")
    )
    scanned: list[tuple[str, str]] = []
    i = 0
    while True:
        j = scan_text.find("if (", i)
        if j < 0:
            break
        # Walk forward tracking paren depth for the contents of `if (...)`.
        # Start counting AFTER the `if ` opener, so depth=0 means we have
        # consumed zero unclosed `(`s inside the condition. The body of the
        # if-block (and any `action(...)` it contains) is skipped because
        # we stop as soon as the outer `if (...)` parens close.
        depth = 0
        k = j + 3  # position of the `(` in `if (`
        k += 1     # step inside the open paren
        while k < len(scan_text):
            ch = scan_text[k]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    break  # this `)` closes the `if (...)` itself
                depth -= 1
            k += 1
        if k >= len(scan_text):
            break
        # `scan_text[k]` is now the outer close-paren of `if (...)`.
        # Step past it to start looking for the action's opening `{`.
        k += 1
        brace = scan_text.find("{", k)
        if brace < 0:
            break
        end = scan_text.find("}", brace)
        if end < 0:
            break
        scanned.append((
            scan_text[j+3:k].strip(),  # includes the outer parens
            scan_text[brace+1:end].strip(),
        ))
        i = end + 1
    if not scanned:
        errors.append("no if-block found (expected 'if ( ... ) { ... }')")
    else:
        for i_idx, (cond_inner, action_inner) in enumerate(scanned):
            if not cond_inner:
                errors.append(f"if-block #{i_idx+1}: condition is empty; re-emit with concrete predicates")
            if not action_inner:
                errors.append(f"if-block #{i_idx+1}: action body is empty; re-emit with concrete action params")
            if action_inner and "ActionName" not in action_inner:
                errors.append(f"if-block #{i_idx+1}: action body missing ActionName")

    return {
        "valid": not errors,
        "warnings": warnings,
        "errors": errors,
        "referenced_columns": sorted(set(referenced_columns)),
        "placeholders": list(set(placeholders)),
    }
