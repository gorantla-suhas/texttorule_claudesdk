# Action catalog reference

The `action_catalog.yaml` is the source of truth for action types.
This file is a quick textual index for the agent. Read on demand.

## Categories

- **benefit**: data_bonus, voice_bonus, sms_bonus, monetary_credit
- **subscription**: subscribe, unsubscribe, switch_plan
- **lifecycle**: winback, retention, upgrade, downgrade
- **communication**: send_offer, send_sms, send_ussd
- **threshold**: throttle, cap, uncap

For each action type, the catalog defines:

- `required_params`: list of param keys that must be present
- `optional_params`: list of param keys that may be present
- `default_params`: dict of param → default value applied when the
  user did not specify them
- `product_family`: which product catalog family the action binds to
  (null for actions that don't bind a product)
