"""Server entry point.

Run with:

    uvicorn app.server:app --host 0.0.0.0 --port 8000

or use the script:

    ./scripts/run_api.sh
"""

from __future__ import annotations

import uvicorn

from app.api import app  # re-export for `uvicorn app.server:app`
from app.config import load_settings
from app.logging import configure_logging


configure_logging()
settings = load_settings()


if __name__ == "__main__":
    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level=settings.log_level.lower(),
    )
