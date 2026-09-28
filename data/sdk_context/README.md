# sdk_context/

Drop any reference material here for the SDK to read on demand.
The orchestrator's `Read` tool can access any file in this tree.

Suggested subfolders (create as needed):

- `catalogs/`     — product, bonus, policy, schedule catalogs (text/JSON/YAML)
- `examples/`     — golden cases and few-shot examples
- `docs/`         — business docs, glossary, runbooks
- `policies/`     — tenant-specific policy overrides
- `seeds/`        — seed templates / reusable condition patterns

Anything you put here becomes agent-readable context. There is no
fixed schema; name files clearly so the agent can find them.
