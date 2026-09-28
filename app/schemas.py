"""Pydantic models and shared dataclasses.

Pydantic models are used at the API boundary. Internal dataclasses
(e.g. `RuleState`) are passed between the orchestrator and the MCP
tools during a request and never cross the HTTP boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Component shapes (Stage 2 outputs, before the if-block is composed)
# ---------------------------------------------------------------------------


@dataclass
class Benefit:
    """One concrete benefit awarded when the bonus trigger fires.

    `details` keys depend on `type`. For `telco_product` and `voucher`,
    `product_name` is the free-text name from the user; Python resolves
    it to a product_id via the catalog SQL. For `airtime`, `value` is
    the airtime amount and `validity_days` is its own validity.
    `loyalty_points` carries only `value`.

    `success_message` and `error_message` are customer-friendly strings.
    """

    type: Literal["telco_product", "airtime", "loyalty_points", "voucher"]
    details: dict[str, Any]
    success_message: str
    error_message: str


@dataclass
class BonusCriteria:
    """Bonus criteria attached to an action.

    Only `Recharge` is implemented this round. `noOfDays` is the
    bonus-trigger window after the action is delivered — NOT the
    benefit's own validity (which lives on the resolved product row).
    """

    action_type: Literal["Recharge"] = "Recharge"
    value: float = 0.0
    aggregation: Literal["SUM", "COUNT", "RANGE"] = "SUM"
    max_value: float = 0.0
    no_of_times: int = 1
    bonus_threshold: int = 1
    no_of_days: int = 0
    benefits: list[Benefit] = field(default_factory=list)


@dataclass
class ActionBlock:
    """The action part of an if-block branch.

    `ActionName` is fixed to "Send Promotion" this round (the
    point-accumulation fields are reserved for future use). If
    `bonus_criteria` is set, the action delivers first and the bonus
    trigger is watched for the next `noOfDays` days.
    """

    action_name: Literal["Send Promotion"] = "Send Promotion"
    channel: str = "SMS"
    product_id: str = ""
    message: str = ""
    message_id: str = ""
    reward_bucket: str = ""
    multiplier: str = ""
    reward_point: str = ""
    point_validity: str = ""
    bonus_criteria: BonusCriteria | None = None


@dataclass
class ScheduleBlock:
    """One schedule block — exactly one per intermediate rule.

    Mirrors the 9-type schema from
    `data/sdk_context/schedule`. Claude picks one `schedule_type` and
    fills the relevant fields; `validate_schedule_json` rejects the
    block if required fields for that type are missing.

    Date fields are ISO `YYYY-MM-DD` here; Python converts to
    `DD/MM/YYYY` when populating the final JSON.
    """

    schedule_type: Literal[
        "ScheduleNow", "Daily", "DailyWithInterval",
        "Weekly", "WeeklyWithInterval",
        "Monthly", "MonthlyWithInterval", "MonthlyWithSpecifics",
        "Interval",
    ] = "ScheduleNow"
    repeat: str = ""
    last_fetch: str | None = None
    segment_rule_start_date: str | None = None
    segment_rule_end_date: str | None = None
    interval: str = ""
    frequency: str = ""
    hours: str = ""
    minutes: str = ""
    type: str | None = None
    period: str = ""
    week: str = ""
    day: str = ""
    select_days: list[str | int] = field(default_factory=list)
    start_time: dict[str, str] = field(default_factory=dict)
    end_time: dict[str, str] = field(default_factory=dict)


@dataclass
class IntermediateRule:
    """One composed intermediate rule.

    `if_blocks` is one entry per branch (one for single-rule, two or
    more for if/else-if). The schedule is shared across all branches
    (exactly one per statement).
    """

    if_blocks: list[dict[str, Any]] = field(default_factory=list)
    schedule: ScheduleBlock | None = None


@dataclass
class FinalRule:
    """The final rule JSON the campaign engine consumes.

    Top-level shape: `{detail: {rules: <tree>, schedule: {...}}}`.
    The Python parser produces this directly; Pydantic mirrors it at
    the API boundary.
    """

    detail: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------


class RuleBuildRequest(BaseModel):
    """Inbound request to the `/rule/build` endpoint."""

    model_config = ConfigDict(extra="forbid")

    client: Literal["omantel", "airtel"]
    sentence: str = Field(min_length=1)
    request_id: str | None = Field(default=None, min_length=1)
    session_id: str | None = Field(default=None, min_length=1)
    user_id: str | None = Field(default=None, min_length=1)


class RuleBuildResponse(BaseModel):
    """Outbound response from `/rule/build`."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    mode: Literal["agent"] = "agent"
    request_id: str
    session_id: str
    orchestrator_model: str
    subagent_model: str
    client: str
    sentence: str

    # Stage outputs
    intermediate_rule: str | None = None     # the if-block string Claude emitted
    final_rule_json: dict[str, Any] | None = None   # the id/pid tree
    validation_verdict: Literal["proceed", "clarify", "decompose"] | None = None
    clarification_question: str | None = None
    user_message: str | None = None

    # Resolved selections (audit)
    selected_columns: list[str] = Field(default_factory=list)
    selected_products: list[str] = Field(default_factory=list)
    selected_action_id: int | None = None
    seed_id: str | None = None

    # Outcome
    needs_clarification: bool = False
    failure_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Internal shared state (per-request)
# ---------------------------------------------------------------------------


@dataclass
class RuleState:
    """Shared per-request state, owned by the orchestrator.

    The orchestrator decides which fields to populate. Python tools
    read and write the fields the orchestrator has asked them to. This
    dataclass is request-scoped — it is created at the start of a
    request and discarded when the request completes.
    """

    request_id: str
    client: str
    sentence: str

    # Stage 1 — validation
    validation_verdict: str | None = None          # "proceed" | "clarify" | "decompose"
    validation_question: str | None = None
    validation_warnings: list[str] = field(default_factory=list)

    # Stage 2 — component reasoning
    normalized_slots: dict[str, Any] | None = None
    condition: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    bonus: dict[str, Any] | None = None
    schedule: dict[str, Any] | None = None

    # Stage 3 / 5 — emitted rule
    intermediate_rule: str | None = None
    intermediate_validation: dict[str, Any] | None = None
    final_rule_json: dict[str, Any] | None = None
    user_message: str | None = None

    # KPIs the orchestrator has actually retrieved this request.
    # Every `kpi` field in the emitted if-block must trace back to one
    # of these (or to `kpis.csv` directly).
    approved_kpis: set[str] = field(default_factory=set)

    # Verifier audit
    verifier_used: bool = False
    verifier_report: dict[str, Any] | None = None

    # Orchestrator bookkeeping
    needs_clarification: bool = False
    clarification_question: str | None = None
    failure_reason: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    audit_log: list[dict[str, Any]] = field(default_factory=list)