# parser — SKILL.md

Compose the intermediate if-block string. Final stage before validation.

## Tool

`mcp__rule__render_intermediate_rule` — emits the if-block string from your component objects.

## Inputs

```python
{
  "if_blocks": [{
    "branch": "if" | "else_if",
    "condition": {"predicates": [...], "logic": "AND|OR"},
    "action": {
      "action_name": "Send Promotion",
      "channel": "SMS",
      "product_id": "",
      "message": "<marketer's text>"
    }
  }, ...],
  "schedule": {...9-type dict...},
  "client": "<client>"
}
```

## Output

The if-block string. Output shape:

```
# client: <client>
if ( <condition> ) {
  action(ActionName="Send Promotion", CHANNEL="<X>", PRODUCT_ID="", MESSAGE="<...>")
}
schedule(schedule_type="<type>", repeat="Yes|No", ...)
```

## Procedure

1. Build `if_blocks` from the condition + action skills.
2. Build `schedule` from the schedule skill.
3. Call `render_intermediate_rule`. If errors, fix the offending field and retry (max 3).
4. Hand the resulting string to the validation skill.

## Strict rules

- **Never hand-write if-block syntax.** Use the tool.
- **Never silently drop a field.** If the action skill gave you MESSAGE, pass it through.
- **One schedule per rule.** Multiple branches share it.
- **No bonus this round.** `bonus_criteria` is not in the input shape.