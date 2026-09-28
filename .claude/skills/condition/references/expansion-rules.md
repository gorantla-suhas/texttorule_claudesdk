# KPI retrieval expansion rules

Reference material for the `condition` skill. Read on demand when
ambiguity is detected.

## When to expand a role

A retrieval role is "unresolved" if **every** returned candidate adds an
unrequested business qualifier:

- `prepaid` / `postpaid`
- `incoming` / `outgoing`
- `local` / `idd` / `international`
- `onnet` / `offnet`
- `roaming`
- `bundle` / `payg` / `free`
- a fixed specialty period (e.g. `eid_2024`)

If the unresolved role has more candidates, call `retrieve_kpis` again
with the same `audit_id` and `page=2` (ranks 6–10), then `page=3` (ranks
11–15). Expansion must have a concrete trigger.

## When NOT to expand

- A role already has a valid candidate.
- The missing candidate would only differ in metadata (display name,
  description wording) from one already accepted.
- The user explicitly named a qualifier and the top candidate matches.
