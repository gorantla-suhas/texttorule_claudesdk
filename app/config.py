"""Runtime configuration.

Loads environment variables, project paths, and tenant settings. The
rest of the codebase imports from this module rather than reading
environment variables directly.

Override any value via environment variables (see `.env.example`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


# ---------------------------------------------------------------------------
# .env auto-load
# ---------------------------------------------------------------------------
# Load variables from a `.env` file in the project root if one exists.
# Existing shell env vars take precedence (override=True).
# No-op if `python-dotenv` is missing or `.env` doesn't exist.

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]

    _ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_DIR: Path = Path(__file__).resolve().parents[1]
CONFIGS_DIR: Path = PROJECT_DIR / "configs"
DATA_DIR: Path = PROJECT_DIR / "data"
SDK_CONTEXT_DIR: Path = DATA_DIR / "sdk_context"
CLAUDE_DIR: Path = PROJECT_DIR / ".claude"
LOGS_DIR: Path = PROJECT_DIR / "logs"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Settings:
    """Runtime settings, loaded once per process."""

    # --- data ---
    data_dir: Path = DATA_DIR
    configs_dir: Path = CONFIGS_DIR
    sdk_context_dir: Path = SDK_CONTEXT_DIR
    audit_dir: Path = LOGS_DIR

    # --- models ---
    orchestrator_model: str = "claude-sonnet-4-5"
    subagent_model: str = "claude-haiku-4-5"
    max_turns: int = 25

    # --- retrieval ---
    embedding_backend: str = "char_ngram"   # char_ngram | sentence-transformers
    retrieval_top_k: int = 5
    bm25_weight: float = 0.5
    embedding_weight: float = 0.5

    # --- observability ---
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://us.cloud.langfuse.com"
    langfuse_environment: str = "development"

    # --- misc ---
    log_level: str = "INFO"
    enable_console_trace: bool = False
    extra_env: dict = field(default_factory=dict)


@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Build the `Settings` object from the current environment."""

    return Settings(
        data_dir=Path(os.environ.get("RULE_DATA_DIR", str(DATA_DIR))),
        configs_dir=Path(os.environ.get("RULE_CONFIGS_DIR", str(CONFIGS_DIR))),
        sdk_context_dir=Path(os.environ.get("RULE_SDK_CONTEXT_DIR", str(SDK_CONTEXT_DIR))),
        audit_dir=Path(os.environ.get("RULE_AUDIT_DIR", str(LOGS_DIR))),
        orchestrator_model=os.environ.get("RULE_ORCHESTRATOR_MODEL", "claude-sonnet-4-5"),
        subagent_model=os.environ.get("RULE_SUBAGENT_MODEL", "claude-haiku-4-5"),
        max_turns=int(os.environ.get("RULE_MAX_TURNS", "25")),
        embedding_backend=os.environ.get("RULE_EMBEDDING_BACKEND", "char_ngram"),
        retrieval_top_k=int(os.environ.get("RULE_RETRIEVAL_TOP_K", "5")),
        bm25_weight=float(os.environ.get("RULE_BM25_WEIGHT", "0.5")),
        embedding_weight=float(os.environ.get("RULE_EMBEDDING_WEIGHT", "0.5")),
        langfuse_enabled=os.environ.get("LANGFUSE_ENABLED", "false").lower() == "true",
        langfuse_public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
        langfuse_base_url=os.environ.get("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com"),
        langfuse_environment=os.environ.get("LANGFUSE_TRACING_ENVIRONMENT", "development"),
        log_level=os.environ.get("RULE_LOG_LEVEL", "INFO"),
        enable_console_trace=os.environ.get("RULE_CONSOLE_TRACE", "0") == "1",
    )
