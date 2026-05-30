"""Pluggable vector store for the deputation corpus.

Two backends behind one interface:
  * LocalVectorStore  — SQLite + numpy. Zero infra, the default.
  * PgVectorStore     — Postgres + pgvector, used when DATABASE_URL is set.

The store is deliberately thin: it persists records and fetches candidate sets
(optionally filtered by neighborhood). Ranking — dense cosine, BM25, RRF, MMR —
lives in retrieve.py so both backends share identical ranking behaviour. At
hackathon corpus sizes (thousands of letters) fetching candidates and ranking in
Python is more than fast enough.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

import numpy as np

from opposition_generator import config


@dataclass
class Deputation:
    deputation_id: str
    neighborhood: str
    text: str
    concerns: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    project_type: str = ""
    embedding: list[float] = field(default_factory=list)


class LocalVectorStore:
    """SQLite-backed store. Embeddings are kept as float32 blobs."""

    def __init__(self, path=None, dim: int | None = None):
        self.path = str(path or config.SQLITE_PATH)
        self.dim = dim
        config.ensure_data_dir()
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deputations (
                deputation_id TEXT PRIMARY KEY,
                neighborhood  TEXT,
                text          TEXT,
                concerns      TEXT,
                groups        TEXT,
                project_type  TEXT,
                embedding     BLOB
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_neighborhood ON deputations(neighborhood)"
        )
        self._conn.commit()

    def reset(self) -> None:
        self._conn.execute("DELETE FROM deputations")
        self._conn.commit()

    def upsert_many(self, deps: list[Deputation]) -> None:
        rows = [
            (
                d.deputation_id,
                d.neighborhood,
                d.text,
                json.dumps(d.concerns),
                json.dumps(d.groups),
                d.project_type,
                np.asarray(d.embedding, dtype=np.float32).tobytes(),
            )
            for d in deps
        ]
        self._conn.executemany(
            """
            INSERT INTO deputations
                (deputation_id, neighborhood, text, concerns, groups, project_type, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(deputation_id) DO UPDATE SET
                neighborhood=excluded.neighborhood,
                text=excluded.text,
                concerns=excluded.concerns,
                groups=excluded.groups,
                project_type=excluded.project_type,
                embedding=excluded.embedding
            """,
            rows,
        )
        self._conn.commit()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM deputations").fetchone()[0]

    def fetch(self, neighborhood: str | None = None) -> list[Deputation]:
        if neighborhood:
            cur = self._conn.execute(
                "SELECT deputation_id, neighborhood, text, concerns, groups, project_type, embedding "
                "FROM deputations WHERE neighborhood = ?",
                (neighborhood,),
            )
        else:
            cur = self._conn.execute(
                "SELECT deputation_id, neighborhood, text, concerns, groups, project_type, embedding "
                "FROM deputations"
            )
        return [_row_to_dep(row) for row in cur.fetchall()]


class PgVectorStore:
    """Postgres + pgvector backend. Used when DATABASE_URL is set.

    Imports are lazy so the local backend never requires psycopg/pgvector.
    """

    def __init__(self, dsn: str, dim: int):
        import psycopg  # noqa: F401  (validated at import time)
        from pgvector.psycopg import register_vector

        self.dsn = dsn
        self.dim = dim
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self._conn)
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS deputation_embeddings (
                deputation_id TEXT PRIMARY KEY,
                neighborhood  TEXT,
                text          TEXT,
                concerns      JSONB,
                groups        JSONB,
                project_type  TEXT,
                embedding     VECTOR({dim})
            )
            """
        )

    def reset(self) -> None:
        self._conn.execute("TRUNCATE deputation_embeddings")

    def upsert_many(self, deps: list[Deputation]) -> None:
        for d in deps:
            self._conn.execute(
                """
                INSERT INTO deputation_embeddings
                    (deputation_id, neighborhood, text, concerns, groups, project_type, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (deputation_id) DO UPDATE SET
                    neighborhood=EXCLUDED.neighborhood, text=EXCLUDED.text,
                    concerns=EXCLUDED.concerns, groups=EXCLUDED.groups,
                    project_type=EXCLUDED.project_type, embedding=EXCLUDED.embedding
                """,
                (
                    d.deputation_id,
                    d.neighborhood,
                    d.text,
                    json.dumps(d.concerns),
                    json.dumps(d.groups),
                    d.project_type,
                    np.asarray(d.embedding, dtype=np.float32),
                ),
            )

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM deputation_embeddings").fetchone()[0]

    def fetch(self, neighborhood: str | None = None) -> list[Deputation]:
        sql = (
            "SELECT deputation_id, neighborhood, text, concerns, groups, project_type, embedding "
            "FROM deputation_embeddings"
        )
        params: tuple = ()
        if neighborhood:
            sql += " WHERE neighborhood = %s"
            params = (neighborhood,)
        cur = self._conn.execute(sql, params)
        out = []
        for row in cur.fetchall():
            dep_id, hood, text, concerns, groups, ptype, emb = row
            out.append(
                Deputation(
                    deputation_id=dep_id,
                    neighborhood=hood,
                    text=text,
                    concerns=concerns if isinstance(concerns, list) else json.loads(concerns or "[]"),
                    groups=groups if isinstance(groups, list) else json.loads(groups or "[]"),
                    project_type=ptype or "",
                    embedding=list(np.asarray(emb, dtype=np.float32)),
                )
            )
        return out


def _row_to_dep(row) -> Deputation:
    dep_id, hood, text, concerns, groups, ptype, emb_blob = row
    embedding = np.frombuffer(emb_blob, dtype=np.float32).tolist() if emb_blob else []
    return Deputation(
        deputation_id=dep_id,
        neighborhood=hood,
        text=text,
        concerns=json.loads(concerns or "[]"),
        groups=json.loads(groups or "[]"),
        project_type=ptype or "",
        embedding=embedding,
    )


def get_store(dim: int | None = None):
    """Return the configured store backend (pgvector if DATABASE_URL else SQLite)."""
    if config.DATABASE_URL:
        if dim is None:
            raise ValueError("PgVectorStore requires an embedding dimension")
        return PgVectorStore(config.DATABASE_URL, dim)
    return LocalVectorStore(dim=dim)
