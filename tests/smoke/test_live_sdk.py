"""Live SDK smoke test. Skipped unless ANTHROPIC_API_KEY is set.

Run with:
    pytest -m smoke
or directly:
    python scripts/smoke_sdk.py
"""

import os

import pytest

from app.orchestrator import run_request
from app.schemas import RuleState


SMOKE_SENTENCE = (
    "Give 5GB data bonus to prepaid users with recharge > 50 OMR "
    "in the last 30 days."
)


@pytest.mark.smoke
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)
@pytest.mark.asyncio
async def test_live_sdk_smoke():
    state = RuleState(
        request_id="smoke-1", client="omantel", sentence=SMOKE_SENTENCE
    )
    messages = []
    async for m in run_request(state):
        messages.append(m)
    assert messages
