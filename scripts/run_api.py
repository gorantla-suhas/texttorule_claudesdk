"""Start the FastAPI server. Activates the venv and runs uvicorn."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
BIN = VENV / "Scripts" if (VENV / "Scripts").exists() else VENV / "bin"
PY = BIN / "python.exe" if (VENV / "Scripts").exists() else BIN / "python"


def main() -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    return subprocess.call(
        [str(PY), "-m", "uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"],
        env=env, cwd=ROOT,
    )


if __name__ == "__main__":
    sys.exit(main())
