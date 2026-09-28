"""Schedule catalog lookup + JSON shape validation — Stage 2d MCP tool.

Reads `configs/schedule_catalog.yaml` and validates a candidate
schedule dict against the 9-type schema (per
`data/sdk_context/schedule`).

Pure Python, deterministic, no I/O.
"""

from __future__ import annotations

import re
from typing import Any


# The 9 schedule types this round. (The catalog uses different names —
# see mapping below.)
SCHEDULE_TYPES: tuple[str, ...] = (
    "ScheduleNow",
    "Daily",
    "DailyWithInterval",
    "Weekly",
    "WeeklyWithInterval",
    "Monthly",
    "MonthlyWithInterval",
    "MonthlyWithSpecifics",
    "Interval",
)


# Required field names per schedule_type. Missing required → invalid.
_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "ScheduleNow": (),
    "Daily": ("day",),
    "DailyWithInterval": ("day", "interval", "start_time"),
    "Weekly": ("day", "select_days"),
    "WeeklyWithInterval": ("day", "select_days", "interval", "start_time"),
    "Monthly": ("day", "select_days"),
    "MonthlyWithInterval": ("day", "select_days", "interval", "start_time"),
    "MonthlyWithSpecifics": ("type", "period", "day", "select_days"),
    "Interval": ("interval",),
}


# Catalog mapping: the YAML uses high-level types ("one_off",
# "recurring", "rolling", "blackout_aware"). The 9-type schema uses
# specific recurrence patterns. This map is the bridge for when
# Claude asks "is this schedule_type valid".
_CATALOG_TO_SCHEDULE: dict[str, str] = {
    "one_off": "ScheduleNow",
    "recurring": "Weekly",         # most common recurring; Claude may
                                    # further specify Daily / Monthly / etc.
    "rolling": "Interval",         # rolling = repeated interval
    "blackout_aware": "Weekly",    # recurring with blackouts
}


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _parse_written_date(text: str, default_year: int | None = None) -> str | None:
    """Parse '10 February 2025' / 'February 10, 2025' / 'YYYY-MM-DD' → 'YYYY-MM-DD'.

    Tolerates ordinal suffixes on the day ('22nd', '1st', '23rd', '3rd').
    If a year is missing and `default_year` is provided, uses it.
    """

    s = (text or "").strip().rstrip(".")
    # Strip ordinal suffixes from the day (22nd -> 22, 1st -> 1, etc.).
    s = re.sub(r"(\d{1,2})(st|nd|rd|th)\b", r"\1", s, flags=re.IGNORECASE)

    m = re.match(r"^(\d{1,2})\s+(\w+)\s+(\d{4})$", s)
    if m:
        d, month_name, y = m.group(1), m.group(2).lower(), int(m.group(3))
        if month_name in _MONTHS:
            return f"{y:04d}-{_MONTHS[month_name]:02d}-{int(d):02d}"
    # Day + month without year — fill from default_year.
    m = re.match(r"^(\d{1,2})\s+(\w+)$", s)
    if m and default_year is not None:
        d, month_name = m.group(1), m.group(2).lower()
        if month_name in _MONTHS:
            return f"{default_year:04d}-{_MONTHS[month_name]:02d}-{int(d):02d}"
    m = re.match(r"^(\w+)\s+(\d{1,2}),?\s+(\d{4})$", s)
    if m:
        month_name, d, y = m.group(1).lower(), m.group(2), int(m.group(3))
        if month_name in _MONTHS:
            return f"{y:04d}-{_MONTHS[month_name]:02d}-{int(d):02d}"
    # Month + day without year.
    m = re.match(r"^(\w+)\s+(\d{1,2})$", s)
    if m and default_year is not None:
        month_name, d = m.group(1).lower(), m.group(2)
        if month_name in _MONTHS:
            return f"{default_year:04d}-{_MONTHS[month_name]:02d}-{int(d):02d}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return s
    return None


import datetime as _dt

# When the sentence says "22nd january" without a year, treat it as the
# current calendar year. The "to/till" date with an explicit year (like
# "23 march 2027") anchors the schedule's actual range.
_TODAY = _dt.date.today()


def _schedule_from_sentence(sentence: str) -> dict[str, Any]:
    """Pick a schedule_type + fields from the marketer sentence.

    Returns a dict ready for `render_intermediate_rule`'s schedule arg.
    Falls back to ScheduleNow if nothing matches.
    """

    s = (sentence or "").strip().lower()

    # Interval: "every N hours/minutes/days"
    m = _INTERVAL_RE_SENT.search(s)
    interval = ""
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if "hour" in unit:
            interval = f"00:{n:02d}:00"
        elif "minute" in unit:
            interval = f"00:00:{n:02d}"
        else:
            interval = f"{n:02d}:00:00"

    # Date range. Look for explicit year first; if either side has a
    # year, use it as the anchor (so "from 22nd january to 23 march 2027"
    # → start=2027-01-22, end=2027-03-23).
    start_raw = end_raw = None
    fm = _FROM_RE_SENT.search(s)
    tm = _TO_RE_SENT.search(s)
    if fm:
        start_raw = fm.group(1)
    if tm:
        end_raw = tm.group(1)

    anchor_year = _TODAY.year
    if end_raw:
        parsed_year = re.search(r"\b(\d{4})\b", end_raw)
        if parsed_year:
            anchor_year = int(parsed_year.group(1))
    elif start_raw:
        parsed_year = re.search(r"\b(\d{4})\b", start_raw)
        if parsed_year:
            anchor_year = int(parsed_year.group(1))

    start = _parse_written_date(start_raw, default_year=anchor_year) if start_raw else None
    end = _parse_written_date(end_raw, default_year=anchor_year) if end_raw else None

    # Daily / weekly / monthly heuristics.
    schedule_type = "ScheduleNow"
    repeat = "No"
    select_days: list[str] = []
    if "now" in s or "immediately" in s:
        schedule_type = "ScheduleNow"
    elif "daily" in s or "every day" in s:
        schedule_type = "Daily"
        repeat = "Yes"
    elif "weekly" in s or any(d in s for d in _WEEKDAYS):
        schedule_type = "Weekly"
        repeat = "Yes"
        for day in _WEEKDAYS:
            if day in s:
                select_days.append(day[:3].upper())
    elif "monthly" in s:
        schedule_type = "Monthly"
        repeat = "Yes"
    elif interval:
        schedule_type = "Interval"
        repeat = "Yes"

    if schedule_type == "ScheduleNow" and (interval or start or end):
        schedule_type = "Interval"
        repeat = "Yes"

    return {
        "schedule_type": schedule_type,
        "repeat": repeat,
        "interval": interval,
        "segment_rule_start_date": start,
        "segment_rule_end_date": end,
        "select_days": select_days,
    }


_INTERVAL_RE_SENT = re.compile(r"every\s+(\d+)\s+(hours?|minutes?|days?)", re.I)
_FROM_RE_SENT = re.compile(r"(?:from|starting\s+from)\s+(\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2})", re.I)
_TO_RE_SENT = re.compile(r"(?:to|until|till|through)\s+(\d{1,2}\s+\w+\s+\d{4}|\d{4}-\d{2}-\d{2})", re.I)
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _schedule_from_sentence(sentence: str) -> dict[str, Any]:
    """Pick a schedule_type + fields from the marketer sentence.

    Returns a dict ready for `render_intermediate_rule`'s schedule arg.
    Falls back to ScheduleNow if nothing matches.
    """

    s = (sentence or "").strip().lower()

    # Interval: "every N hours/minutes/days"
    m = _INTERVAL_RE_SENT.search(s)
    interval = ""
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if "hour" in unit:
            interval = f"00:{n:02d}:00"
        elif "minute" in unit:
            interval = f"00:00:{n:02d}"
        else:
            interval = f"{n:02d}:00:00"

    # Date range.
    start = None
    end = None
    fm = _FROM_RE_SENT.search(s)
    tm = _TO_RE_SENT.search(s)
    if fm:
        start = _parse_written_date(fm.group(1))
    if tm:
        end = _parse_written_date(tm.group(1))

    # Daily / weekly / monthly heuristics.
    schedule_type = "ScheduleNow"
    repeat = "No"
    select_days: list[str] = []
    if "now" in s or "immediately" in s:
        schedule_type = "ScheduleNow"
    elif "daily" in s or "every day" in s:
        schedule_type = "Daily"
        repeat = "Yes"
    elif "weekly" in s or any(d in s for d in _WEEKDAYS):
        schedule_type = "Weekly"
        repeat = "Yes"
        for day in _WEEKDAYS:
            if day in s:
                select_days.append(day[:3].upper())
    elif "monthly" in s:
        schedule_type = "Monthly"
        repeat = "Yes"
    elif interval:
        schedule_type = "Interval"
        repeat = "Yes"

    if schedule_type == "ScheduleNow" and (interval or start or end):
        schedule_type = "Interval"
        repeat = "Yes"

    return {
        "schedule_type": schedule_type,
        "repeat": repeat,
        "interval": interval,
        "segment_rule_start_date": start,
        "segment_rule_end_date": end,
        "select_days": select_days,
    }


def lookup_schedule(phrase: str, client: str | None = None) -> dict[str, Any]:
    """Return the selected schedule + a list of all valid types.

    `phrase` is the cadence phrase OR the full marketer sentence.
    If a schedule can be inferred, `selected` is populated and ready
    for the render tool. `valid_types` and `hints` are always returned.
    """

    if not phrase or not phrase.strip():
        return {
            "valid_types": list(SCHEDULE_TYPES),
            "phrase": phrase,
            "hints": _HINTS,
            "selected": None,
        }

    selected = _schedule_from_sentence(phrase)
    return {
        "valid_types": list(SCHEDULE_TYPES),
        "phrase": phrase,
        "hints": _HINTS,
        "selected": selected,
    }


# Lightweight hints Claude can use to pick a type. Not exhaustive.
_HINTS: dict[str, str] = {
    "run now":            "ScheduleNow",
    "immediately":        "ScheduleNow",
    "every day":          "Daily",
    "every Monday":        "Weekly",
    "every Mon":           "Weekly",
    "weekly on Monday":   "Weekly",
    "every N hours":      "Interval",
    "every 2 hours":      "Interval",
    "every 30 minutes":   "Interval",
    "monthly on the 15th": "Monthly",
    "first Monday":       "MonthlyWithSpecifics",
}


def validate_schedule_dict(schedule: dict[str, Any]) -> dict[str, Any]:
    """Validate a schedule dict against the 9-type schema.

    Output:

        {
          "valid": bool,
          "errors": ["<message>", ...],
          "schedule_type": "<echo | unknown>",
          "warnings": ["<message>", ...]
        }
    """

    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(schedule, dict):
        return {"valid": False, "errors": ["schedule must be a dict"], "schedule_type": None, "warnings": []}

    st = schedule.get("schedule_type")
    if not st:
        errors.append("schedule_type is required")
        return {"valid": False, "errors": errors, "schedule_type": None, "warnings": []}

    if st not in SCHEDULE_TYPES:
        errors.append(
            f"schedule_type '{st}' is not one of {list(SCHEDULE_TYPES)}"
        )
        return {"valid": False, "errors": errors, "schedule_type": st, "warnings": []}

    for required in _REQUIRED_FIELDS.get(st, ()):
        if required not in schedule or schedule[required] in (None, "", [], {}):
            errors.append(f"schedule_type '{st}' requires field '{required}'")

    # Type-specific sanity checks (warnings, not errors).
    if st in ("Weekly", "WeeklyWithInterval", "MonthlyWithSpecifics"):
        sd = schedule.get("select_days")
        if not sd:
            warnings.append(f"select_days should be populated for '{st}'")

    if "interval" in schedule and schedule["interval"]:
        iv = str(schedule["interval"])
        if not _INTERVAL_RE.match(iv):
            errors.append(f"interval '{iv}' does not match DD:HH:MM format (zero-padded)")

    # Date format check (ISO).
    for date_field in ("segment_rule_start_date", "segment_rule_end_date"):
        v = schedule.get(date_field)
        if v is not None and v != "":
            if not _ISO_DATE_RE.match(str(v)):
                errors.append(f"{date_field} '{v}' does not match YYYY-MM-DD")

    return {
        "valid": not errors,
        "errors": errors,
        "schedule_type": st,
        "warnings": warnings,
    }


import re as _re

_INTERVAL_RE = _re.compile(r"^\d{2}:\d{2}:\d{2}$")
_ISO_DATE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")


__all__ = [
    "lookup_schedule",
    "validate_schedule_dict",
    "SCHEDULE_TYPES",
    "_CATALOG_TO_SCHEDULE",
]