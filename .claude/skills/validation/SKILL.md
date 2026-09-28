# validation — SKILL.md

Decide: `proceed` (one rule), `decompose` (N branches), or `clarify` (need user input). After the rule is built, run `validate_intermediate_rule` for the final technical check.

## Tool

`mcp__rule__extract_segment_markers` — returns candidate split positions.

## Procedure

1. Call the tool once. Read the marker list.
2. Decide the verdict from the full sentence context:
   - **`decompose`** — the sentence contains "otherwise", "else if", "else", "for the rest", "for other users", or two clearly different subscriber segments.
   - **`clarify`** — action verb missing, no targeting clause, or a KPI phrase is genuinely ambiguous.
   - **`proceed`** — otherwise.
3. After the parser skill renders the if-block, call:
   ```
   mcp__rule__validate_intermediate_rule({intermediate_rule: "<string>", client: "<client>"})
   ```
4. If `valid: false`, send the errors back to the parser skill to fix and re-render.

## Heuristics

- Strong split markers: `otherwise`, `else if`, `else`, `for the rest`, `for other users`.
- One verdict per call.
- Clarification text must be plain English. No internal column/group/table names.
- Do not call other tools when verdict is `clarify`.