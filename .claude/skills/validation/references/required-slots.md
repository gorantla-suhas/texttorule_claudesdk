# Required slots per intent

This file is **reference material only**. The agent reads it on demand,
not by default.

| Intent              | Required slots                                              |
|---------------------|-------------------------------------------------------------|
| `bonus_eligibility` | `action`, `bonus`, `metric` (or filter chain), `time_window` |
| `offer_targeting`   | `action`, `audience_filter`, `time_window`                   |
| `subscription`      | `action`, `product`, `audience_filter`, `time_window`        |
| `threshold_rule`    | `metric`, `operator`, `value`, `time_window`                 |
| `lifecycle`         | `audience_filter`, `transition`, `time_window`               |

If any required slot cannot be parsed and has no safe default, the
verdict is `needs_clarification`.
