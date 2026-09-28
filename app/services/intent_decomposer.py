"""Intent decomposition — the single LLM call in the pipeline.

The model takes a marketer's natural-language sentence and returns
a structured `Intent` JSON. Everything downstream is pure code.

The model is intentionally given a tight, typed schema and a small
example set. It does NOT:
- Look up KPIs
- Pick action types from the YAML
- Parse dates or convert units
- Decide aggregation strategies

It only does: NL → typed JSON.

If the model is unsure, it says so explicitly in `ambiguities` or
`missing_required` and the pipeline stops with a clarification
question.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from app.config import load_settings
from app.services.intent_models import (
    Action,
    Audience,
    AudienceExclusion,
    AudienceFilter,
    BenefitSpec,
    Bonus,
    BonusTier,
    BonusTrigger,
    Intent,
    Schedule,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

DECOMPOSE_PROMPT = """\
You are a senior telecom campaign planner. Extract the structured
intent from a marketer's sentence. Return ONLY valid JSON — no prose,
no markdown fences.

A "campaign intent" has UP TO 5 concerns:

1. audience    - who the campaign targets
2. action      - what the campaign does
3. bonuses     - conditional rewards (optional)
4. schedule    - when to run (optional; defaults to "now")
5. ambiguities / missing_required - explicit flags

For each filter, capture the marketer's exact phrase and any time
phrase. The downstream code resolves them to KPIs, action types,
and time buckets.

# OUTPUT SCHEMA

{
  "intent": {
    "audience": {
      "filters": [
        {"phrase": "<user words for ONE condition>", "time": "<user time phrase or 'current'>", "value_hint": "<optional numeric/operator hint>"}
      ],
      "exclusions": [
        {"phrase": "<user words for exclusion>", "time": "<user time phrase or 'current'>"}
      ]
    },
    "action": {
      "verb":     "<send|grant|apply|activate|notify|winback|re-engage|offer>",
      "noun":     "<what to send/grant/apply>",
      "intent_text": "<free-text marketer goal - becomes the message>",
      "channel_hint": "<SMS|EMAIL|USSD|null>"
    },
    "bonuses": [
      {
        "trigger": {
          "phrase":  "<user words for the trigger event>",
          "channel": "<optional: MOBILE_APP|RETAIL|IVR|...>",
          "metric":  "<optional: recharge amount|usage|...>",
          "time":    "<optional: next|within X days|...>"
        },
        "tiers": [
          {
            "range": [<lo>, <hi or null>],
            "benefits": [
              {"type": "data|voice|sms|monetary|loyalty_points|voucher", "amount": "<user text>"}
            ]
          }
        ]
      }
    ],
    "schedule": {
      "phrase": "<user words for cadence, or empty>",
      "start":  "<user date text, or null>",
      "end":    "<user date text, or null>"
    },
    "ambiguities":      ["<anything unclear>"],
    "missing_required": ["<audience|action|schedule>"]
  }
}

# RULES

1. Filters: each is ONE condition. "prepaid users who recharged more than 50 OMR last month"
   → two filters: {"phrase":"prepaid users","time":"current"} and {"phrase":"recharged more than 50 OMR","time":"last month"}.
2. Exclusions: words like "but not", "exclude", "excluding", "except".
3. Action.verb: pick the closest. "send X" → "send". "grant X" → "grant". "apply X" → "apply".
4. Action.intent_text: the user's free-text goal. Empty if none.
5. Action.channel_hint: if the user named a channel ("SMS", "email"). null otherwise.
6. Bonuses: extract ONLY if the sentence has a conditional reward.
   - "if they recharge X, give Y" → tier with range=[X, null].
   - "give 5 GB for 10-20, 15 GB for 20-50" → two tiers.
   - "30 GB plus 300 voice minutes" → two benefits in ONE tier.
   - Tier range [lo, hi]: numbers from the user. hi=null means "and above".
7. Schedule.phrase: "every 4 hours", "daily at 9am", "weekly on Monday", "now", "every 12 hours from 10 Feb to 10 Mar".
   - If no cadence, leave phrase empty (defaults to ScheduleNow).
8. ambiguities: list any part you genuinely cannot resolve. DO NOT guess.
9. missing_required: ["audience"] if no audience, ["action"] if no action, etc.
   - Missing schedule is OK (defaults to ScheduleNow).
   - Missing bonuses is OK (no bonus block).
   - Empty ambiguities + missing_required = fully resolvable.

# EXAMPLES

Input: "Send a promotional SMS to prepaid users who recharged more than 50 OMR last month, with a 10 GB bonus if they recharge between 6 and 10 RO. Run every 4 hours from 10 Feb 2025 to 10 March 2026."
Output: {
  "intent": {
    "audience": {
      "filters": [
        {"phrase": "prepaid users", "time": "current"},
        {"phrase": "recharged more than 50 OMR", "time": "last month"}
      ],
      "exclusions": []
    },
    "action": {"verb": "send", "noun": "promotional SMS", "intent_text": "", "channel_hint": "SMS"},
    "bonuses": [{
      "trigger": {"phrase": "recharge between 6 and 10 RO", "channel": null, "metric": "recharge amount", "time": "next"},
      "tiers": [{"range": [6, 10], "benefits": [{"type": "data", "amount": "10 GB"}]}]
    }],
    "schedule": {"phrase": "every 4 hours", "start": "10 February 2025", "end": "10 March 2026"},
    "ambiguities": [],
    "missing_required": []
  }
}

Input: "Send SMS to all customers today."
Output: {
  "intent": {
    "audience": {"filters": [{"phrase": "all customers", "time": "current"}], "exclusions": []},
    "action":    {"verb": "send", "noun": "SMS", "intent_text": "", "channel_hint": "SMS"},
    "bonuses":   [],
    "schedule":  {"phrase": "now", "start": null, "end": null},
    "ambiguities": [],
    "missing_required": []
  }
}

Input: "Give 10 GB to users who recharge >20."
Output: {
  "intent": {
    "audience": {"filters": [{"phrase": "recharged more than 20 OMR", "time": "current"}], "exclusions": []},
    "action":   {"verb": "grant", "noun": "10 GB", "intent_text": "", "channel_hint": null},
    "bonuses":  [],
    "schedule": {"phrase": "", "start": null, "end": null},
    "ambiguities": [],
    "missing_required": []
  }
}

# INPUT

Sentence: {sentence}

Return ONLY the JSON. No commentary.
"""


# ---------------------------------------------------------------------------
# Heuristic fallback (no model available)
# ---------------------------------------------------------------------------

_KEYWORD_VERBS = {
    "send": "send", "grant": "grant", "give": "grant", "apply": "apply",
    "activate": "activate", "notify": "notify", "winback": "winback",
    "win back": "winback", "re-engage": "re-engage", "reengage": "re-engage",
    "offer": "offer",
}


def _heuristic_decompose(sentence: str) -> Intent:
    """A best-effort, model-free fallback. Used when LLM is unavailable.

    Handles simple patterns: action verb + audience + optional bonus.
    Far less capable than the LLM but never blocks the pipeline.
    """

    s = sentence.strip()
    lowered = s.lower()

    # Action
    verb = "send"
    for k, v in _KEYWORD_VERBS.items():
        if lowered.startswith(k) or f" {k} " in lowered:
            verb = v
            break

    noun_match = re.search(r"\b(send|grant|give|apply|activate|notify)\b\s+(.*?)(?:\s+to\s+|\s+for\s+|$)", lowered)
    noun = noun_match.group(2).strip() if noun_match else ""

    # Channel
    channel_hint: str | None = None
    if "sms" in lowered:
        channel_hint = "SMS"
    elif "email" in lowered:
        channel_hint = "EMAIL"
    elif "ussd" in lowered:
        channel_hint = "USSD"

    # Audience
    filters: list[AudienceFilter] = []
    exclusions: list[AudienceExclusion] = []
    to_match = re.search(r"\bto\s+(.*?)(?:\.|,|;|$)", s, re.IGNORECASE)
    if to_match:
        audience_text = to_match.group(1).strip()
        filters.append(AudienceFilter(phrase=audience_text, time="current"))

    # Heuristic ambiguities
    ambiguities: list[str] = []
    missing_required: list[str] = []
    if not filters:
        missing_required.append("audience")

    return Intent(
        audience=Audience(filters=filters, exclusions=exclusions),
        action=Action(verb=verb, noun=noun, intent_text="", channel_hint=channel_hint),
        bonuses=[],
        schedule=Schedule(),
        ambiguities=ambiguities,
        missing_required=missing_required,
    )


# ---------------------------------------------------------------------------
# Decomp. entry point
# ---------------------------------------------------------------------------

def _coerce_intent(raw: dict[str, Any]) -> Intent:
    """Coerce the model's JSON (loose typed) into the strict Intent dataclass."""

    intent = raw.get("intent", raw) if isinstance(raw, dict) else {}

    audience_raw = intent.get("audience", {}) or {}
    filters: list[AudienceFilter] = []
    for f in audience_raw.get("filters", []) or []:
        if isinstance(f, dict) and f.get("phrase"):
            filters.append(AudienceFilter(
                phrase=str(f["phrase"]).strip(),
                time=str(f.get("time") or "current").strip(),
                value_hint=f.get("value_hint"),
            ))
    exclusions: list[AudienceExclusion] = []
    for e in audience_raw.get("exclusions", []) or []:
        if isinstance(e, dict) and e.get("phrase"):
            exclusions.append(AudienceExclusion(
                phrase=str(e["phrase"]).strip(),
                time=str(e.get("time") or "current").strip(),
            ))

    action_raw = intent.get("action", {}) or {}
    action = Action(
        verb=str(action_raw.get("verb") or "send").strip(),
        noun=str(action_raw.get("noun") or "").strip(),
        intent_text=str(action_raw.get("intent_text") or "").strip(),
        channel_hint=action_raw.get("channel_hint"),
    )

    bonuses: list[Bonus] = []
    for b in intent.get("bonuses", []) or []:
        if not isinstance(b, dict):
            continue
        trigger_raw = b.get("trigger", {}) or {}
        trigger = BonusTrigger(
            phrase=str(trigger_raw.get("phrase") or "").strip(),
            channel=trigger_raw.get("channel"),
            metric=trigger_raw.get("metric"),
            time=trigger_raw.get("time"),
        )
        tiers: list[BonusTier] = []
        for t in b.get("tiers", []) or []:
            if not isinstance(t, dict):
                continue
            rng = t.get("range") or [None, None]
            if not isinstance(rng, list) or len(rng) < 2:
                continue
            lo, hi = rng[0], rng[1]
            try:
                lo = float(lo) if lo is not None else None
            except (TypeError, ValueError):
                lo = None
            if hi is not None:
                try:
                    hi = float(hi)
                except (TypeError, ValueError):
                    hi = None
            benefits: list[BenefitSpec] = []
            for bnf in t.get("benefits", []) or []:
                if isinstance(bnf, dict) and bnf.get("type") and bnf.get("amount"):
                    type_str = str(bnf["type"]).strip().lower()
                    if type_str not in ("data", "voice", "sms", "monetary", "loyalty_points", "voucher"):
                        continue
                    benefits.append(BenefitSpec(
                        type=type_str,  # type: ignore[arg-type]
                        amount=str(bnf["amount"]).strip(),
                    ))
            tiers.append(BonusTier(range=[lo, hi], benefits=benefits))
        bonuses.append(Bonus(trigger=trigger, tiers=tiers))

    schedule_raw = intent.get("schedule", {}) or {}
    schedule = Schedule(
        phrase=str(schedule_raw.get("phrase") or "").strip(),
        start=schedule_raw.get("start"),
        end=schedule_raw.get("end"),
    )

    ambiguities = [str(a) for a in (intent.get("ambiguities") or []) if a]
    missing_required = [str(m) for m in (intent.get("missing_required") or []) if m]

    return Intent(
        audience=Audience(filters=filters, exclusions=exclusions),
        action=action,
        bonuses=bonuses,
        schedule=schedule,
        ambiguities=ambiguities,
        missing_required=missing_required,
    )


def decompose_intent(sentence: str, *, use_model: bool = True) -> Intent:
    """Decompose a sentence into an Intent.

    If `use_model=True`, calls the configured LLM (single call). If
    the model is unavailable or the response is malformed, falls back
    to a heuristic.
    """

    if not use_model or not _model_available():
        log.info("decompose: heuristic mode (model disabled or unavailable)")
        return _heuristic_decompose(sentence)

    try:
        raw = _call_model(sentence)
        return _coerce_intent(raw)
    except Exception as exc:
        log.exception("decompose: model failed, falling back to heuristic: %s", exc)
        return _heuristic_decompose(sentence)


# ---------------------------------------------------------------------------
# Model plumbing
# ---------------------------------------------------------------------------

def _model_available() -> bool:
    """True if the configured LLM endpoint is reachable enough to try."""

    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_BASE_URL"))


def _call_model(sentence: str) -> dict[str, Any]:
    """Single LLM call returning the decomposed JSON.

    Talks to the configured provider via the OpenAI-compatible
    /v1/chat/completions endpoint (which is what both Ollama's
    local models and Ollama's cloud models expose, as well as
    Anthropic via the `anthropic` SDK shim).

    Falls back to plain Ollama /api/chat if /v1/chat/completions
    doesn't respond.
    """

    import urllib.request
    import urllib.error
    import socket

    settings = load_settings()
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "http://localhost:11434").rstrip("/")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "ollama")
    model = settings.orchestrator_model
    # DECOMPOSE_PROMPT contains example JSON with braces; use a literal
    # replace rather than str.format to avoid KeyError on the JSON.
    prompt = DECOMPOSE_PROMPT.replace("{sentence}", sentence)

    # Try OpenAI-compatible /v1/chat/completions first.
    url = f"{base_url}/v1/chat/completions"
    payload = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    text = ""
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # OpenAI shape.
        choices = data.get("choices") or []
        if choices:
            text = choices[0].get("message", {}).get("content", "") or ""
    except (urllib.error.HTTPError, urllib.error.URLError, socket.timeout, KeyError, json.JSONDecodeError) as exc:
        log.warning("decompose: OpenAI-compat endpoint failed (%s); trying /api/chat", exc)
        # Fall back to plain Ollama /api/chat.
        url2 = f"{base_url}/api/chat"
        payload2 = json.dumps({
            "model": model,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 2000},
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req2 = urllib.request.Request(
            url2, data=payload2,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = data.get("message") or {}
        text = msg.get("content", "") or ""

    if not text:
        raise RuntimeError("model returned empty response")

    return _extract_json(text)


def _extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from the model's text response."""

    text = text.strip()
    # Strip optional markdown fences.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    # Find the first { that opens a top-level object.
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in model response")
    # Walk forward to find the matching brace.
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                return json.loads(candidate)
    raise ValueError("unbalanced JSON in model response")


__all__ = ["decompose_intent", "DECOMPOSE_PROMPT", "Intent"]
