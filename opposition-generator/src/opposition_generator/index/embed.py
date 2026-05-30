"""Embeddings via Ollama, plus the corpus index builder.

Embeddings come from the Ollama server (see config.OLLAMA_URL / EMBED_MODEL).
`build_index()` reads the deputation corpus and writes embeddings into whichever
vector store config selects (SQLite by default, pgvector when DATABASE_URL set).
"""

from __future__ import annotations

import time

import httpx

from opposition_generator import config
from opposition_generator.index.corpus import load_corpus
from opposition_generator.index.store import Deputation, get_store

_MAX_RETRIES = 4


class EmbeddingError(RuntimeError):
    """Raised when the embedding backend is unreachable or misbehaves."""


def embed_text(text: str) -> list[float]:
    """Embed a single string. Raises EmbeddingError on any failure."""
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings via Ollama.

    Ollama's /api/embeddings takes one prompt at a time, so we loop. Each request
    is retried with backoff because a busy Ollama (e.g. mid large-model load)
    occasionally returns a transient 500, which shouldn't abort a whole index build.
    """
    url = f"{config.OLLAMA_URL}/api/embeddings"
    out: list[list[float]] = []
    with httpx.Client(timeout=config.EMBED_TIMEOUT_S) as client:
        for text in texts:
            # truncate to stay within the embedding model's context window
            out.append(_embed_one(client, url, text[: config.EMBED_MAX_CHARS]))
    return out


def _embed_one(client: httpx.Client, url: str, text: str) -> list[float]:
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = client.post(url, json={"model": config.EMBED_MODEL, "prompt": text})
            resp.raise_for_status()
            vec = resp.json().get("embedding")
            if not vec:
                raise EmbeddingError(f"empty embedding for text: {text[:60]!r}")
            return [float(x) for x in vec]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            last_err = exc
            time.sleep(1.5 * (attempt + 1))  # linear backoff: 1.5s, 3s, 4.5s
    raise EmbeddingError(
        f"embedding backend {url} (model={config.EMBED_MODEL}) failed after "
        f"{_MAX_RETRIES} attempts: {last_err}"
    )


def build_index() -> int:
    """Embed the full deputation corpus into the vector store.

    Returns the number of deputations indexed. Idempotent — resets and rebuilds.
    """
    records = load_corpus()
    if not records:
        raise RuntimeError(
            "No deputation corpus found. Run `opposition-generator seed` to load the "
            "sample corpus, or `opposition-generator scrape` to ingest from TMMIS."
        )

    texts = [r["text"] for r in records]
    embeddings = embed_batch(texts)
    dim = len(embeddings[0])

    store = get_store(dim=dim)
    store.reset()
    deps = [
        Deputation(
            deputation_id=r["deputation_id"],
            neighborhood=r["neighborhood"],
            text=r["text"],
            concerns=r.get("concerns", []),
            groups=r.get("groups", []),
            project_type=r.get("project_type", ""),
            embedding=emb,
        )
        for r, emb in zip(records, embeddings)
    ]
    store.upsert_many(deps)
    return len(deps)


if __name__ == "__main__":
    n = build_index()
    print(f"Indexed {n} deputations into the vector store.")
