"""Central configuration for opposition-generator.

Everything external is env-driven so the component runs three ways without code
changes:

  * Local dev (default): SQLite vector store + Ollama on localhost. Zero infra.
  * Shared GB10: same, pointing at the box's already-running Ollama.
  * Production: set DATABASE_URL to use Postgres + pgvector instead of SQLite.

The model backends (embeddings + LLM) are served by Ollama. The README scaffold
named sentence-transformers + Qwen2.5; we use Ollama instead because it is the
shared inference server already running on the GB10 and avoids a torch install.
The contract (`generate`) is unchanged — the model backend is the owner's call.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- paths ---
PACKAGE_ROOT = Path(__file__).resolve().parent
COMPONENT_ROOT = PACKAGE_ROOT.parent.parent  # opposition-generator/
DATA_DIR = Path(os.getenv("OPP_DATA_DIR", COMPONENT_ROOT / "data"))

# --- Ollama (embeddings + generation) ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.getenv("OPP_EMBED_MODEL", "nomic-embed-text")
LLM_MODEL = os.getenv("OPP_LLM_MODEL", "nemotron-3-super:latest")
# Ingest tagging is a high-volume, low-stakes extraction task; allow a faster model.
TAG_MODEL = os.getenv("OPP_TAG_MODEL", LLM_MODEL)
# nomic-embed-text is 768-dim; mxbai-embed-large is 1024. The store reads the
# dimension from the first vector it sees, so this only needs to match the model.
# Generous by default: a cold load of a 30B+ model can take >2 min on first call.
# Embedding inputs are truncated to this many chars: real deputations can exceed
# nomic-embed-text's 2048-token context, which makes Ollama 500. 4000 chars stays
# safely under 2048 tokens even for token-dense text; the opening of a deputation
# carries its position + concerns, and BM25 still indexes the full text.
EMBED_MAX_CHARS = int(os.getenv("OPP_EMBED_MAX_CHARS", "4000"))
LLM_TIMEOUT_S = float(os.getenv("OPP_LLM_TIMEOUT_S", "300"))
EMBED_TIMEOUT_S = float(os.getenv("OPP_EMBED_TIMEOUT_S", "120"))
# Keep the model resident between calls so HyDE + letter generation stay warm.
LLM_KEEP_ALIVE = os.getenv("OPP_LLM_KEEP_ALIVE", "30m")

# --- vector store ---
# If DATABASE_URL is set we use pgvector; otherwise a local SQLite file.
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. postgresql://hack:hack@localhost:5432/hack_nima
SQLITE_PATH = Path(os.getenv("OPP_SQLITE_PATH", DATA_DIR / "deputations.sqlite3"))

# --- retrieval ---
DEFAULT_TOP_K = int(os.getenv("OPP_TOP_K", "8"))


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
