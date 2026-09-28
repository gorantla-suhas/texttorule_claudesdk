"""Typed dataclasses for the Intent → Rule pipeline.

The flow is:

    NL sentence
        ↓
    IntentDecomposer  (1 LLM call)
        ↓ returns: Intent
    IntentResolver    (pure code, no LLM)
        ↓ returns: ResolvedComponents
    compose_intermediate_rule
        ↓ returns: if-block string
    parse_intermediate_to_final
        ↓ returns: final id/pid tree

All fields are typed so the resolver can be tested without a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Decomposition output (one per independent statement)
# ---------------------------------------------------------------------------


@dataclass
class AudienceFilter:
    """One positive audience filter.

    `phrase` is the user's natural language for the filter.
    `time` is the time window phrase ("last 30 days", "previous month",
    "current", "normally", "next" etc.). The resolver normalizes
    `time` into a time_bucket.
    `value_hint` is optional user-given value (e.g. ">50" for
    "recharged more than 50 OMR"). The resolver still uses `phrase`
    for KPI lookup; `value_hint` only helps operator inference.
    """

    phrase: str
    time: str = "current"
    value_hint: str | None = None


@dataclass
class AudienceExclusion:
    """One negative filter (excludes)."""

    phrase: str
    time: str = "current"


@dataclass
class Audience:
    """The audience for one intent."""

    filters: list[AudienceFilter] = field(default_factory=list)
    exclusions: list[AudienceExclusion] = field(default_factory=list)


@dataclass
class Action:
    """The action the campaign triggers.

    `intent_text` is the marketer's free-text goal (e.g. "Encourage
    use of the mobile app"). It becomes the `MESSAGE` field in the
    campaign engine.
    `channel_hint` is optional ("SMS", "EMAIL"). The resolver picks
    the actual channel from the matched action_type if not given.
    """

    verb: str = "send"
    noun: str = ""
    intent_text: str = ""
    channel_hint: str | None = None


@dataclass
class BenefitSpec:
    """One benefit (raw, from the user)."""

    type: Literal["data", "voice", "sms", "monetary", "loyalty_points", "voucher"]
    amount: str  # raw text, e.g. "5 GB", "300 minutes", "10 RO"


@dataclass
class BonusTier:
    """One tier of a bonus.

    `range` is [lo, hi]. A `None` hi means "and above".
    """

    range: list[float | None]
    benefits: list[BenefitSpec] = field(default_factory=list)


@dataclass
class BonusTrigger:
    """What triggers the bonus (raw, user phrase)."""

    phrase: str
    channel: str | None = None
    metric: str | None = None  # e.g. "recharge amount"
    time: str | None = None    # "next", "within X days"


@dataclass
class Bonus:
    """A conditional bonus.

    `trigger` describes WHEN the bonus fires.
    `tiers` is the list of reward tiers (one per recharge range).
    If a bonus has no tiers (e.g. "give them 5 GB"), it has one
    tier with `range=[None, None]` and the matching benefits.
    """

    trigger: BonusTrigger
    tiers: list[BonusTier] = field(default_factory=list)


@dataclass
class Schedule:
    """The schedule for the campaign."""

    phrase: str = ""
    start: str | None = None
    end: str | None = None


@dataclass
class Intent:
    """One decomposed intent (one independent rule)."""

    audience: Audience = field(default_factory=Audience)
    action: Action = field(default_factory=Action)
    bonuses: list[Bonus] = field(default_factory=list)
    schedule: Schedule = field(default_factory=Schedule)
    ambiguities: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Resolver output (typed, ready for the if-block)
# ---------------------------------------------------------------------------


@dataclass
class ResolvedFilter:
    """One resolved audience filter, ready to render into the if-block."""

    kpi: str                       # resolved KPI column name
    operator: str                  # =, >, <, BETWEEN, IN LIST, ...
    value: Any                     # the comparison value
    time_bucket: str = "NONE"      # 30D, M1, LATEST, NONE, ...
    table: str = ""                # the table the KPI lives in
    data_type: str = "string"      # numeric, string, date
    date_column: str = ""          # FCT_DT etc.
    phrase: str = ""               # original user phrase (audit)
    role: str = "filter"           # metric, filter, time


@dataclass
class ResolvedAction:
    """The resolved action, ready to render."""

    action_name: str = "Send Promotion"
    action_type: str = "send_sms"
    channel: str = "SMS"
    message: str = ""
    message_id: str = ""
    product_id: str = ""
    action_id: int | None = None
    required_params_filled: dict[str, Any] = field(default_factory=dict)
    missing_required: list[str] = field(default_factory=list)


@dataclass
class ResolvedBenefit:
    """One resolved benefit, with product_id from SQL."""

    type: str               # canonical: data_bonus, voice_bonus, ...
    subtype: str            # data, voice, sms, monetary, ...
    amount_mb: int | None = None
    minutes: int | None = None
    count: int | None = None
    amount: float | None = None
    currency: str | None = None
    product_id: str | None = None
    success_message: str = "113"
    error_message: str = "114"
    raw_text: str = ""


@dataclass
class ResolvedTier:
    """One resolved bonus tier."""

    range: list[float | None]
    criteria: dict[str, Any]       # the BONUS_CRITERIA inner struct
    benefits: list[ResolvedBenefit] = field(default_factory=list)


@dataclass
class ResolvedBonus:
    """One resolved bonus (may have multiple tiers)."""

    trigger_phrase: str
    criteria_template: dict[str, Any]   # action_type, aggregation, etc.
    tiers: list[ResolvedTier] = field(default_factory=list)


@dataclass
class ResolvedSchedule:
    """The resolved schedule, ready to render."""

    schedule_type: str = "ScheduleNow"
    repeat: str = "No"
    last_fetch: str | None = None
    interval: str = ""
    segment_rule_start_date: str | None = None
    segment_rule_end_date: str | None = None
    frequency: str = ""
    hours: str = ""
    minutes: str = ""
    type: str | None = None
    period: str = ""
    week: str = ""
    day: str = ""
    select_days: list[Any] = field(default_factory=list)
    start_time: dict[str, str] = field(default_factory=dict)
    end_time: dict[str, str] = field(default_factory=dict)
    schedule_struct: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResolvedComponents:
    """All components resolved, ready for the if-block composer."""

    audience_filters: list[ResolvedFilter] = field(default_factory=list)
    audience_exclusions: list[ResolvedFilter] = field(default_factory=list)
    action: ResolvedAction = field(default_factory=ResolvedAction)
    bonuses: list[ResolvedBonus] = field(default_factory=list)
    schedule: ResolvedSchedule = field(default_factory=ResolvedSchedule)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ambiguous: list[dict[str, Any]] = field(default_factory=list)  # KPIs that were ambiguous
    not_found: list[dict[str, Any]] = field(default_factory=list)  # phrases that resolved to nothing


# ---------------------------------------------------------------------------
# Pipeline outcome
# ---------------------------------------------------------------------------


@dataclass
class PipelineOutcome:
    """The final outcome of a request."""

    ok: bool
    needs_clarification: bool = False
    clarification_question: str | None = None
    failure_reason: str | None = None
    intermediate_rule: str | None = None
    final_rule_json: dict[str, Any] | None = None
    user_message: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    selected_columns: list[str] = field(default_factory=list)
    selected_products: list[str] = field(default_factory=list)
    selected_action_id: int | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "AudienceFilter",
    "AudienceExclusion",
    "Audience",
    "Action",
    "BenefitSpec",
    "BonusTier",
    "BonusTrigger",
    "Bonus",
    "Schedule",
    "Intent",
    "ResolvedFilter",
    "ResolvedAction",
    "ResolvedBenefit",
    "ResolvedTier",
    "ResolvedBonus",
    "ResolvedSchedule",
    "ResolvedComponents",
    "PipelineOutcome",
]
