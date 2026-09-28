"""CLI entry point — `rule-engine "..." --client omantel`.

Designed for local smoke testing and CI. For production traffic, use
the FastAPI server in `app.server`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.config import load_settings
from app.observability import configure_langfuse
from app.orchestrator import run_request
from app.schemas import RuleState


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rule-engine",
        description="Convert a natural-language campaign rule into structured Rule JSON.",
    )
    parser.add_argument("sentence", help="The campaign rule in plain English.")
    parser.add_argument(
        "--client",
        required=True,
        choices=["omantel", "airtel"],
        help="Tenant identifier.",
    )
    parser.add_argument("--request-id", default=None)
    parser.add_argument("--debug-sdk", action="store_true")
    parser.add_argument("--trace-file", default=None, help="Write SDK trace to this path.")
    return parser


async def _run(args: argparse.Namespace) -> int:
    settings = load_settings()
    configure_langfuse()

    state = RuleState(
        request_id=args.request_id or "cli",
        client=args.client,
        sentence=args.sentence,
    )

    chunks: list[str] = []
    try:
        async for message in run_request(state, debug_sdk=args.debug_sdk):
            text = getattr(message, "result", None)
            if isinstance(text, str) and text.strip():
                chunks.append(text)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 2

    print(json.dumps({"ok": True, "chunks": chunks, "model": settings.orchestrator_model}, indent=2))
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
