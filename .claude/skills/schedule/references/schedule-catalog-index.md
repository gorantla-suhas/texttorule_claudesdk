# Schedule catalog reference

`configs/schedule_catalog.yaml` defines schedule types. Quick index.

## Schedule types

- `one_off` — single execution window (start, end)
- `recurring` — repeated execution at a fixed cadence (daily / weekly /
  monthly)
- `rolling` — continuous evaluation over a moving window (the rule fires
  any time the audience condition is met in the window)
- `blackout_aware` — recurring with explicit blackout windows

Each entry defines:

- `default_window`: rolling window default (`null` if not applicable)
- `requires_start`, `requires_end`: booleans
- `supported_recurrences`: list of supported recurrence frequencies
- `timezone_default`: the timezone assumed when not specified
