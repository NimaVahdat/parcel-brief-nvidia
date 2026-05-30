"""Pluggable vector store for the precedent corpus.

SQLite + numpy by default (zero infra); pgvector when DATABASE_URL is set. Thin by
design — ranking (dense + BM25 + RRF + MMR) lives in retrieve.py. Each precedent is
a past Toronto planning application with its known council outcome.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

import numpy as np

from vote_predictor import config


@dataclass
class Precedent:
    precedent_id: str
    text: str                       # embedded text (project descriptor, outcome stripped)
    outcome: str                    # "approved" | "refused"
    ward: str = ""
    committee: str = ""
    year: int = 0
    app_type: str = ""
    address: str = ""
    votes: dict = field(default_factory=dict)   # {councillor_id: "yes"|"no"}, sparse
    embedding: list[float] = field(default_factory=list)


class LocalVectorStore:
    def __init__(self, path=None, dim: int | None = None):
        self.path = str(path or config.SQLITE_PATH)
        self.dim = dim
        config.ensure_data_dir()
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS precedents (
                precedent_id TEXT PRIMARY KEY,
                text TEXT, outcome TEXT, ward TEXT, committee TEXT,
                year INTEGER, app_type TEXT, address TEXT, votes TEXT, embedding BLOB
            )
            """
        )
        self._conn.commit()

    def reset(self) -> None:
        self._conn.execute("DELETE FROM precedents")
        self._conn.commit()

    def upsert_many(self, items: list[Precedent]) -> None:
        rows = [
            (
                p.precedent_id, p.text, p.outcome, p.ward, p.committee, p.year,
                p.app_type, p.address, json.dumps(p.votes),
                np.asarray(p.embedding, dtype=np.float32).tobytes(),
            )
            for p in items
        ]
        self._conn.executemany(
            """
            INSERT INTO precedents
                (precedent_id, text, outcome, ward, committee, year, app_type, address, votes, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(precedent_id) DO UPDATE SET
                text=excluded.text, outcome=excluded.outcome, ward=excluded.ward,
                committee=excluded.committee, year=excluded.year, app_type=excluded.app_type,
                address=excluded.address, votes=excluded.votes, embedding=excluded.embedding
            """,
            rows,
        )
        self._conn.commit()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM precedents").fetchone()[0]

    def fetch(self, exclude_id: str | None = None) -> list[Precedent]:
        cur = self._conn.execute(
            "SELECT precedent_id, text, outcome, ward, committee, year, app_type, "
            "address, votes, embedding FROM precedents"
        )
        out = []
        for row in cur.fetchall():
            if exclude_id and row[0] == exclude_id:
                continue
            out.append(_row_to_precedent(row))
        return out


class PgVectorStore:
    """Postgres + pgvector backend (used when DATABASE_URL is set)."""

    def __init__(self, dsn: str, dim: int):
        import psycopg
        from pgvector.psycopg import register_vector

        self.dsn, self.dim = dsn, dim
        self._conn = psycopg.connect(dsn, autocommit=True)
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(self._conn)
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS precedents (
                precedent_id TEXT PRIMARY KEY, text TEXT, outcome TEXT, ward TEXT,
                committee TEXT, year INTEGER, app_type TEXT, address TEXT,
                votes JSONB, embedding VECTOR({dim})
            )
            """
        )

    def reset(self) -> None:
        self._conn.execute("TRUNCATE precedents")

    def upsert_many(self, items: list[Precedent]) -> None:
        for p in items:
            self._conn.execute(
                """
                INSERT INTO precedents (precedent_id, text, outcome, ward, committee,
                    year, app_type, address, votes, embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (precedent_id) DO UPDATE SET text=EXCLUDED.text,
                    outcome=EXCLUDED.outcome, ward=EXCLUDED.ward, committee=EXCLUDED.committee,
                    year=EXCLUDED.year, app_type=EXCLUDED.app_type, address=EXCLUDED.address,
                    votes=EXCLUDED.votes, embedding=EXCLUDED.embedding
                """,
                (p.precedent_id, p.text, p.outcome, p.ward, p.committee, p.year,
                 p.app_type, p.address, json.dumps(p.votes),
                 np.asarray(p.embedding, dtype=np.float32)),
            )

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM precedents").fetchone()[0]

    def fetch(self, exclude_id: str | None = None) -> list[Precedent]:
        cur = self._conn.execute(
            "SELECT precedent_id, text, outcome, ward, committee, year, app_type, "
            "address, votes, embedding FROM precedents"
        )
        out = []
        for row in cur.fetchall():
            if exclude_id and row[0] == exclude_id:
                continue
            votes = row[8] if isinstance(row[8], dict) else json.loads(row[8] or "{}")
            out.append(Precedent(
                precedent_id=row[0], text=row[1], outcome=row[2], ward=row[3],
                committee=row[4], year=row[5] or 0, app_type=row[6] or "",
                address=row[7] or "", votes=votes,
                embedding=list(np.asarray(row[9], dtype=np.float32)),
            ))
        return out


def _row_to_precedent(row) -> Precedent:
    emb = np.frombuffer(row[9], dtype=np.float32).tolist() if row[9] else []
    return Precedent(
        precedent_id=row[0], text=row[1], outcome=row[2], ward=row[3] or "",
        committee=row[4] or "", year=row[5] or 0, app_type=row[6] or "",
        address=row[7] or "", votes=json.loads(row[8] or "{}"), embedding=emb,
    )


def get_store(dim: int | None = None):
    if config.DATABASE_URL:
        if dim is None:
            raise ValueError("PgVectorStore requires an embedding dimension")
        return PgVectorStore(config.DATABASE_URL, dim)
    return LocalVectorStore(dim=dim)
