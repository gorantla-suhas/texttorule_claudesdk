# schedule — examples.md

## Example 1 — rolling 30-day window

**Input slots:**
```json
{ "schedule": "rolling_30d" }
```

**Final schedule object:**
```json
{
  "type": "rolling",
  "window": { "value": 30, "unit": "days" },
  "start": null,
  "end": null,
  "recurrence": null,
  "blackouts": []
}
```

---

## Example 2 — one-off tomorrow

**Input slots:**
```json
{ "schedule": "one_off", "start": "tomorrow", "end": "tomorrow" }
```

**Final schedule object (relative placeholders left for runtime):**
```json
{
  "type": "one_off",
  "window": null,
  "start": "${resolve:tomorrow}",
  "end": "${resolve:tomorrow}",
  "recurrence": null,
  "blackouts": []
}
```
