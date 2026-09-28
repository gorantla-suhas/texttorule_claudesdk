# condition — SKILL.md

Resolve the targeting clause for one rule branch. Pick the KPI column from `data/kpis.csv` for each audience filter the user expressed.

## Tool

`mcp__rule__retrieve_kpis` — top-K candidates per role (metric / filter / time).

## Procedure

1. Read each audience phrase from the sentence.
2. Call `retrieve_kpis` once with the phrase(s) and `client`.
3. Pick the best-fit candidate. Reasoning:
   - If the top candidate adds an unrequested business qualifier (prepaid, postpaid, onnet/offnet, IDD, roaming), try the next candidate.
   - For "prepaid" / "postpaid" → the OfferId column (starts with 11/12).
   - For "recharged X" → CUST_360_RECHARGE_AMOUNT_30D / 60D / 90D.
   - For dates, prefer date-typed columns.
4. Decide the operator from the phrase:
   - "more than X" / "over X" / ">" → `>`
   - "less than X" / "under X" / "<" → `<`
   - "at least X" / ">=" → `>=`
   - "at most X" / "<=" → `<=`
   - "X" alone (no operator word) → `=` for strings, `>` for numeric thresholds.
   - "between X and Y" → `BETWEEN` with `[X, Y]`.
5. Build the predicate:
   ```
   {kpi: "<column_name>", operator: ">", value: 50}
   ```

## Strict rules

- One KPI per filter. Multiple filters → join with `AND`.
- Never write condition syntax. The parser skill's `render_intermediate_rule` tool emits.
- Never accept a candidate that adds an unrequested qualifier when a more general one is available.
- If the user gave no numeric threshold, do not invent one — clarify.