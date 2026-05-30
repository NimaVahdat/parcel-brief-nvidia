"""Embed the deputation corpus into pgvector.

Builds the table:
    deputation_embeddings (
        deputation_id TEXT PRIMARY KEY,
        neighborhood TEXT,
        embedding VECTOR(768)
    )

Uses sentence-transformers/all-mpnet-base-v2 (768-dim).
"""

import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://hack:hack@localhost:5432/hack")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
EMBEDDING_DIM = 768


def build_index() -> None:
    """Read data/deputations.parquet, embed all texts, write to pgvector.

    TODO:
    1. Ensure CREATE EXTENSION vector is run (handled by docker-compose init script).
    2. CREATE TABLE IF NOT EXISTS deputation_embeddings (...).
    3. Load sentence-transformers model.
    4. Iterate parquet, batch-encode, INSERT ... ON CONFLICT (deputation_id) DO UPDATE.
    5. CREATE INDEX ON deputation_embeddings USING hnsw (embedding vector_cosine_ops).
    """
    raise NotImplementedError("Wire up sentence-transformers + psycopg + pgvector.")


if __name__ == "__main__":
    build_index()
