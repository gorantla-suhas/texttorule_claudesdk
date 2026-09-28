# Final Rule JSON — quick reference

You do NOT need to read this file. `mcp__rule__parse_intermediate_to_final` produces the `id/pid/childrens` tree the campaign engine consumes. DB lookups (profile_id, action_id, product_id, bonus_details) happen inside the tool.

Shape (for maintainers):

```json
{"detail": {"rules": {"id": "0", "pid": "#", "childrens": [...conditions / condition / action nodes...], "schedule": {"field": [...]}}}}
```

Node IDs are depth-aware (`0`, `0_0`, `0_0_0`, `0_0_0_0`...). Schedule fields use PascalCase (`ScheduleType`, `StartDate`, `ExpiryDate`, `Days`, `Hours`, `Minutes`). Dates are `DD/MM/YYYY` (parser converts from `YYYY-MM-DD`).

If the tool errors, the response contains `{"error": "..."}`. Read it.
