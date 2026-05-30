"""Central configuration for vote-predictor.

Same env-driven, infra-light philosophy as opposition-generator: embeddings via the
shared Ollama server, a pluggable vector store (SQLite default / pgvector via
DATABASE_URL), and an optional LLM only for phrasing. No XGBoost, no training — this
component predicts council outcomes by retrieving similar real past applications.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
COMPONENT_ROOT = PACKAGE_ROOT.parent.parent  # vote-predictor/
DATA_DIR = Path(os.getenv("VP_DATA_DIR", COMPONENT_ROOT / "data"))

# --- Ollama (embeddings + optional phrasing) ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.getenv("VP_EMBED_MODEL", "nomic-embed-text")
LLM_MODEL = os.getenv("VP_LLM_MODEL", "nemotron-3-super:latest")
EMBED_MAX_CHARS = int(os.getenv("VP_EMBED_MAX_CHARS", "4000"))
EMBED_TIMEOUT_S = float(os.getenv("VP_EMBED_TIMEOUT_S", "120"))
LLM_TIMEOUT_S = float(os.getenv("VP_LLM_TIMEOUT_S", "300"))
LLM_KEEP_ALIVE = os.getenv("VP_LLM_KEEP_ALIVE", "30m")

# --- vector store ---
DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_PATH = Path(os.getenv("VP_SQLITE_PATH", DATA_DIR / "precedents.sqlite3"))

# --- retrieval ---
DEFAULT_TOP_K = int(os.getenv("VP_TOP_K", "12"))


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
