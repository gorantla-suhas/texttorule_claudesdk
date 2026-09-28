# validation — examples.md

Few-shot anchors for the validation skill. These are **reasoning
patterns**, not hardcoded rules. The verdict is Claude's, informed
by `mcp__rule__extract_segment_markers` evidence.

---

## Example 1 — `proceed` (single complete rule)

**Input:** "Give 5GB data bonus to prepaid users with recharge > 50 OMR in the last 30 days."

**Reasoning:**
- One targeting clause, one action, one benefit.
- No `otherwise` / `else if` / `for inactive users` markers.
- `extract_segment_markers` returns `[]` or only weak markers
  inside the condition (e.g. "in the last 30 days" — not a
  split marker).
- Schedule is missing from the input but will be inferred by
  Stage 2d from the "last 30 days" time window. Validation does
  **not** flag schedule as missing here.

**Verdict:** `proceed` — single rule, proceed to Stage 2.

---

## Example 2 — `decompose` (multi-segment with `otherwise`)

**Input:** "Send SMS to active users who recharged > 50 OMR in the last 30 days, otherwise offer 5GB bonus to inactive users who recharged > 100 OMR in the last 60 days."

**Reasoning:**
- `otherwise` between two self-contained clauses.
- Each side has its own targeting (active vs inactive), its own
  threshold (50 vs 100), its own time window (30 vs 60).
- `extract_segment_markers` returns `[{position: 71, marker: "otherwise", kind: "split"}]`.

**Verdict:** `decompose` — 2 sub-rules. Orchestrator loops the rest
of the pipeline per branch.

---

## Example 3 — `decompose` (multi-segment with `else if`)

**Input:** "If balance > 10 send offer A. Else if balance < 5 send offer B."

**Reasoning:**
- `else if` is a split marker. Each clause is a separate branch.
- Each branch has its own condition and action.

**Verdict:** `decompose` — 2 sub-rules.

---

## Example 4 — `decompose` (parallel segments)

**Input:** "Send SMS to prepaid users, send offer to postpaid users."

**Reasoning:**
- Two independent clauses describing two distinct subscriber
  segments (prepaid vs postpaid).
- `extract_segment_markers` may or may not return explicit markers
  (no `otherwise` here), but the segment parallelism is the
  signal.

**Verdict:** `decompose` — 2 sub-rules.

---

## Example 5 — `proceed` (with bonus attached — NOT decomposed)

**Input:** "Target prepaid customers who recharged more than 10 RO last month. Send a promotional SMS. If the customer recharges between 6 and 10 RO within 15 days, provide a 10 GB data pack."

**Reasoning:**
- One targeting clause (prepaid + recharge > 10).
- One action: Send a promotional SMS.
- The second sentence ("If the customer recharges between 6 and 10
  RO within 15 days, provide a 10 GB data pack") is a **bonus
  clause attached to the action**, not a new branch.
- Trigger phrase: `and If <condition>, then provide <benefit>`.
- No `otherwise` / `else if` — the clauses are connected by
  imperative, not by mutual exclusion.

**Verdict:** `proceed` — single rule. The 10 GB data pack becomes
`BONUS_CRITERIA` inside the action (Stage 2c).

---

## Example 6 — `clarify` (ambiguous business label)

**Input:** "Send an offer to high-value customers."

**Reasoning:**
- Action present (send offer).
- Targeting uses an ambiguous business label ("high-value
  customer") with no further clarification.
- No safe default — high-value could mean value segment, ARPU,
  total revenue, recharge, or several different KPIs.

**Verdict:** `clarify`.

**Clarification question:** "By 'high-value customer', do you mean
a stored value segment (e.g. VALUE_SEGMENT_OVERALL = HIGH) or a
specific KPI threshold (e.g. total revenue, ARPU, recharge amount
over a period)?"

---

## Example 7 — `clarify` (no action verb)

**Input:** "Prepaid users with recharge > 50 OMR in last 30 days."

**Reasoning:**
- Targeting present but no action verb. The marketer described
  *who*, not *what to do*.

**Verdict:** `clarify`.

**Clarification question:** "What should the campaign do (e.g.
send SMS, apply offer, grant bonus)?"

---

## Example 8 — `clarify` (gibberish / unrelated)

**Input:** "asdfghjkl"

**Verdict:** `clarify`.

**Clarification question:** "I didn't receive a campaign rule to
work with. Could you describe what you want to build?"

---

## Example 9 — `clarify` (empty input)

**Input:** `""`

**Verdict:** `clarify`.

**Clarification question:** "I didn't receive a campaign rule to
work with. Could you describe what you want to build?"

---

## Boundary cases — what the skill must NOT do

- Do NOT decompose when the second clause is a bonus attached to
  the action (Example 5 above). The trigger phrase
  `and if / then provide / then grant` is the signal that it's a
  bonus, not a new branch.
- Do NOT `clarify` for missing schedule. Schedule is decided in
  Stage 2d, and time windows in the condition can be used to infer
  it.
- Do NOT `clarify` for an empty `benefits[]`. The action may still
  be valid without a bonus attached.