# schedule — SKILL.md

One schedule per rule. All branches of one rule share the schedule.

## Tool

`mcp__rule__lookup_schedule` — accepts the sentence, returns `{selected, valid_types, hints}`.

## Procedure

1. Call `lookup_schedule` with the full sentence and `client`.
2. The tool returns `selected` already populated when the sentence contains a cadence phrase. Use it as-is.
3. If `selected` is null, pick a default:
   - "now" / "immediately" / no cadence → `ScheduleNow`.
4. Validate the 9-type schema (see the reference fields below).

## 9 schedule types

| Type | When |
|---|---|
| `ScheduleNow` | "now" / "immediately" |
| `Daily` | "every day at HH:MM" |
| `DailyWithInterval` | "every day HH:MM–HH:MM every N hours" |
| `Weekly` | "every <Day> at HH:MM" |
| `WeeklyWithInterval` | weekly + interval |
| `Monthly` | "on the Nth of every month at HH:MM" |
| `MonthlyWithInterval` | monthly + interval |
| `MonthlyWithSpecifics` | "first/last <Day> of every month" |
| `Interval` | "every N hours/minutes/days" |

## Field shape (pascalCase keys)

```python
{
  "schedule_type": "<one of 9>",
  "repeat": "Yes|No",
  "last_fetch": "Yes|No|null",
  "segment_rule_start_date": "YYYY-MM-DD | null",
  "segment_rule_end_date": "YYYY-MM-DD | null",
  "interval": "DD:HH:MM | \"\"",
  "frequency": "",
  "hours": "",
  "minutes": "",
  "type": "First|Second|...|null",
  "period": "Week|Month | \"\"",
  "week": "1|2|3|4 | \"\"",
  "day": "<string>",
  "select_days": [] | ["MON", ...] | [1, 15, ...],
  "start_time": {"ALL": "HH:MM"} | {},
  "end_time": {"ALL": "HH:MM"} | {}
}
```

## Format

- `9am` / `09:00` → `"09:00"` (24-hour, zero-padded).
- `6 PM` → `"18:00"`.
- `9am to 5pm` → `"09:00–17:00"` (en-dash).
- Date range "from 10 February 2025 to 10 March 2026" → ISO `2025-02-10` / `2026-03-10`.