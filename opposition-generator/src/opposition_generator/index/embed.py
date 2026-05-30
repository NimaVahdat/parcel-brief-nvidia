"""Embeddings via Ollama, plus the corpus index builder.

Embeddings come from the Ollama server (see config.OLLAMA_URL / EMBED_MODEL).
`build_index()` reads the deputation corpus and writes embeddings into whichever
vector store config selects (SQLite by default, pgvector when DATABASE_URL set).
"""

from __future__ import annotations

import httpx

from opposition_generator import config
from opposition_generator.index.corpus import load_corpus
from opposition_generator.index.store import Deputation, get_store


class EmbeddingError(RuntimeError):
    """Raised when the embedding backend is unreachable or misbehaves."""


def embed_text(text: str) -> list[float]:
    """Embed a single string. Raises EmbeddingError on any failure."""
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings via Ollama.

    Ollama's /api/embeddings takes one prompt at a time, so we loop. Kept as a
    batch API so callers (and a future batched backend) don't need to change.
    """
    url = f"{config.OLLAMA_URL}/api/embeddings"
    out: list[list[float]] = []
    try:
        with httpx.Client(timeout=config.EMBED_TIMEOUT_S) as client:
            for text in texts:
                resp = client.post(
                    url, json={"model": config.EMBED_MODEL, "prompt": text}
                )
                resp.raise_for_status()
                vec = resp.json().get("embedding")
                if not vec:
                    raise EmbeddingError(f"empty embedding for text: {text[:60]!r}")
                out.append([float(x) for x in vec])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise EmbeddingError(
            f"embedding backend {url} (model={config.EMBED_MODEL}) failed: {exc}"
        ) from exc
    return out


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
