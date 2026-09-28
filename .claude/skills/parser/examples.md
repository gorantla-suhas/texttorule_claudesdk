# parser — examples.md

## Example — composed template before render

Given the five skill outputs:

```json
{
  "condition": {
    "main_kpi": "recharge_amount_30d",
    "operator": "${operator}",
    "value": "${value}",
    "filters": [{ "column": "subscriber_type", "operator": "=", "value": "prepaid" }],
    "time_window": { "kind": "rolling", "value": 30, "unit": "days" },
    "table": "360_PROFILE"
  },
  "action": { "type": "data_bonus", "product_id": "DATA_BONUS_5GB", "params": { "amount_mb": 5120 } },
  "bonus": { "type": "data", "aggregation": "per_subscriber", "products": ["DATA_BONUS_5GB"] },
  "policy": { "eligibility": { "subscriber_type": "prepaid" }, "exclusions": [], "conflicts": [] },
  "schedule": { "type": "rolling", "window": { "value": 30, "unit": "days" } }
}
```

The parser picks seed `SEED_THRESHOLD_BONUS_V1` and composes the
template (the actual template text is owned by the catalog; this is
the resolved shape after the parser fills it in):

```text
PARENT_CONDITION
subscriber_type = 'prepaid'
AND
recharge_amount_30d ${operator} ${value}

ACTION
data_bonus(product=DATA_BONUS_5GB, amount_mb=5120)

BONUS
data(per_subscriber, [DATA_BONUS_5GB])

POLICY
eligibility: subscriber_type=prepaid
exclusions: []

SCHEDULE
rolling(30d)
```

The `builder` subagent passes this to `render_rule`. The renderer is
the only component that emits the final JSON string.
