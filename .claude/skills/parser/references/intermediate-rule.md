# Intermediate Rule — quick reference

You do NOT need to read this file. The `mcp__rule__render_intermediate_rule` tool emits the if-block string from your component objects. Pass:

```python
{
  "if_blocks": [{
    "branch": "if" | "else_if",
    "condition": {"predicates": [{"kpi": str, "operator": str, "value": ...}], "logic": "AND|OR"},
    "action": {
      "action_name": "Send Promotion",
      "channel": "SMS",
      "product_id": str,
      "message": str
    }
  }, ...],
  "schedule": { /* see schedule skill */ },
  "client": "omantel"
}
```

Operators: `=`, `<>`, `>`, `>=`, `<`, `<=`, `BETWEEN <lo> AND <hi>`, `IN LIST("A", "B")`, `IS NULL`, `LIKE`.

One schedule per statement. Multiple branches share it.

**Reference (do not paste into Claude's context):** the full field grammar is documented for maintainers at this path on disk. If the tool rejects your input, the error message names the offending field.