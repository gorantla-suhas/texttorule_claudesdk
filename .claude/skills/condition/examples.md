# condition — examples.md

## Example 1 — recharge threshold

**Input slots:**
```json
{
  "metric": { "feature": "recharge_amount", "operator": ">", "value": 50, "unit": "OMR" },
  "filters": [{ "feature": "subscriber_type", "value": "prepaid" }],
  "time_window": "last_30_days"
}
```

**retrieve_kpis result (metric role, top 3):**
| id  | feature_name        | group_name        | description                            |
|-----|---------------------|-------------------|----------------------------------------|
| 421 | recharge_amount_30d | 360_PROFILE       | Total recharge amount in last 30 days. |
| 422 | recharge_amount_90d | 360_PROFILE       | Total recharge amount in last 90 days. |
| 518 | recharge_amt_lc     | Recharge_Seg_Fct  | Recharge amount, lifecycle.            |

**Picked:** `recharge_amount_30d` (group `360_PROFILE`, matches
`time_window_value=30d`).

**Final condition object:**
```json
{
  "main_kpi": "recharge_amount_30d",
  "operator": "${operator}",
  "value": "${value}",
  "filters": [
    { "column": "subscriber_type", "operator": "=", "value": "prepaid" }
  ],
  "time_window": { "kind": "rolling", "value": 30, "unit": "days" },
  "table": "360_PROFILE"
}
```
