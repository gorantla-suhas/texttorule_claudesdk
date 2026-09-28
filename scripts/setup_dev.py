"""Dev environment setup. Creates a venv and installs the package."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    venv = ROOT / ".venv"
    if not venv.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv)])
    pip = venv / "Scripts" / "pip.exe" if (venv / "Scripts").exists() else venv / "bin" / "pip"
    subprocess.check_call([str(pip), "install", "-e", ".[dev]"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
