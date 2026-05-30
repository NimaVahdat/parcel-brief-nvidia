"""Embeddings via Ollama (with retry + context-window truncation)."""

from __future__ import annotations

import time

import httpx

from vote_predictor import config

_MAX_RETRIES = 4


class EmbeddingError(RuntimeError):
    """Raised when the embedding backend is unreachable or misbehaves."""


def embed_text(text: str) -> list[float]:
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    url = f"{config.OLLAMA_URL}/api/embeddings"
    out: list[list[float]] = []
    with httpx.Client(timeout=config.EMBED_TIMEOUT_S) as client:
        for text in texts:
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
                raise EmbeddingError(f"empty embedding for: {text[:60]!r}")
            return [float(x) for x in vec]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    raise EmbeddingError(
        f"embedding backend {url} (model={config.EMBED_MODEL}) failed after "
        f"{_MAX_RETRIES} attempts: {last_err}"
    )


def build_index() -> int:
    """Embed the precedent corpus into the vector store. Returns count indexed."""
    from vote_predictor.corpus import load_corpus
    from vote_predictor.store import Precedent, get_store

    records = load_corpus()
    if not records:
        raise RuntimeError("No precedents. Run `vote-predictor seed` or `vote-predictor scrape`.")
    embeddings = embed_batch([r["text"] for r in records])
    store = get_store(dim=len(embeddings[0]))
    store.reset()
    store.upsert_many([
        Precedent(
            precedent_id=r["precedent_id"], text=r["text"], outcome=r["outcome"],
            ward=r["ward"], committee=r["committee"], year=r["year"],
            app_type=r["app_type"], address=r["address"], votes=r["votes"], embedding=e,
        )
        for r, e in zip(records, embeddings)
    ])
    return len(records)
