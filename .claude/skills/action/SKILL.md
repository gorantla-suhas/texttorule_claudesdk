# action — SKILL.md

Pick the business action. This round: only `Send Promotion`.

## Tool

`mcp__rule__lookup_action` — reads the sentence, returns `{selected, channel_inferred}`.

## Procedure

1. Call `lookup_action` with the full sentence and `client`.
2. The tool returns `selected.action_name = "Send Promotion"` and `selected.channel` from the sentence (default `SMS`).
3. Decide MESSAGE:
   - If the user wrote a quoted phrase in the sentence, the tool extracts it as `message`.
   - Otherwise, write a short promotional phrase based on the sentence's noun (e.g. "Exclusive promotion for {noun}").
   - Never leave MESSAGE empty.
4. If channel is genuinely missing and the sentence is ambiguous, clarify.

## Strict rules

- One action per rule. ActionName is always `Send Promotion`.
- Channel comes from the sentence (SMS / EMAIL / IN_APP / USSD / PUSH).
- Never invent product_id or message_id — leave as empty string.
- Never write if-block syntax. The parser skill emits it.