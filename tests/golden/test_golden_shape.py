"""Golden case loader + shape check.

Loads each JSON in data/sdk_context/examples/ and asserts the
expected rule has the required top-level fields. Real semantic
evaluation lives in the agent eval harness.
"""

import json
from pathlib import Path

import pytest

from app.config import DATA_DIR


EXAMPLES_DIR = DATA_DIR / "sdk_context" / "examples"
REQUIRED = {"parent_condition", "action", "policy", "schedule"}


def _cases():
    if not EXAMPLES_DIR.exists():
        return []
    return list(EXAMPLES_DIR.glob("EX_*.json"))


@pytest.mark.parametrize("path", _cases())
def test_golden_shape(path: Path):
    case = json.loads(path.read_text(encoding="utf-8"))
    expected = case["expected_rule"]
    missing = REQUIRED - expected.keys()
    assert not missing, f"{path.name} missing fields: {missing}"
    assert case["sentence"]
    assert case["client"]
