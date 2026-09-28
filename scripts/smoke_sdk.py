"""End-to-end SDK smoke test. Requires ANTHROPIC_API_KEY."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.orchestrator import run_request
from app.schemas import RuleState


DEFAULT_SENTENCE = (
    "Give 5GB data bonus to prepaid users with recharge > 50 OMR "
    "in the last 30 days."
)


async def main(args: argparse.Namespace) -> int:
    state = RuleState(
        request_id=args.request_id or "smoke",
        client=args.client,
        sentence=args.sentence,
    )
    chunks: list[str] = []
    try:
        async for m in run_request(state, debug_sdk=args.debug):
            r = getattr(m, "result", None)
            if isinstance(r, str) and r.strip():
                chunks.append(r)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 2
    print(json.dumps({"ok": True, "chunks": chunks}, indent=2))
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--client", default="omantel", choices=["omantel", "airtel"])
    p.add_argument("--sentence", default=DEFAULT_SENTENCE)
    p.add_argument("--request-id", default=None)
    p.add_argument("--debug", action="store_true")
    raise SystemExit(asyncio.run(main(p.parse_args())))
