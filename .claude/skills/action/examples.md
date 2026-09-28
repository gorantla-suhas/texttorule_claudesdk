# action — examples.md

## Example 1 — data bonus

**Input slots:**
```json
{ "action": "data_bonus", "bonus_size": "5GB" }
```

**lookup_product result:**
```json
{ "product_id": "DATA_BONUS_5GB", "family": "data_bonus", "unit": "MB", "value": 5120 }
```

**Final action object:**
```json
{
  "type": "data_bonus",
  "product_id": "DATA_BONUS_5GB",
  "params": { "amount_mb": 5120 }
}
```

---

## Example 2 — subscription

**Input slots:**
```json
{ "action": "subscribe", "product_name": "weekly data pack" }
```

**lookup_product result:**
```json
{ "product_id": "SUB_WEEKLY_DATA", "family": "subscription", "recurrence": "weekly" }
```

**Final action object:**
```json
{
  "type": "subscribe",
  "product_id": "SUB_WEEKLY_DATA",
  "params": { "recurrence": "weekly" }
}
```
