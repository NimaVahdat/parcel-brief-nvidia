"""Embedding retrieval over real application text via the local nomic-embed-text model.

Replaces the feature-distance similar-case retrieval with semantic similarity over the AIC
``DESCRIPTION`` text, served by nomic-embed-text on the same Ollama box as the reasoning
model (768-dim, verified live). Vectors are cached so retrieval is a cheap matrix product at
predict time. When the endpoint is unreachable (CI, offline), ``is_available`` returns False
and the caller falls back to deterministic feature-distance retrieval — so nothing hard-fails.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from vote_predictor import config


def _embedding_url() -> str:
    """Return the OpenAI-compatible embeddings endpoint URL.

    Returns:
        str: ``{EMBEDDING_BASE_URL}/embeddings``.
    """
    return f"{config.EMBEDDING_BASE_URL.rstrip('/')}/embeddings"


def embed_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Embed a list of texts with the local nomic-embed-text model.

    Args:
        texts (list[str]): Texts to embed.
        batch_size (int): How many texts to send per request.

    Returns:
        numpy.ndarray: An ``(n, EMBEDDING_DIM)`` float array of embeddings.

    Raises:
        httpx.HTTPError: If an embedding request fails.
    """
    import httpx

    vectors: list[list[float]] = []
    headers = {"Authorization": f"Bearer {config.LLM_API_KEY}"}
    with httpx.Client(timeout=config.LLM_TIMEOUT_S) as client:
        for start in range(0, len(texts), batch_size):
            batch = [t or " " for t in texts[start : start + batch_size]]
            response = client.post(
                _embedding_url(),
                json={"model": config.EMBEDDING_MODEL, "input": batch},
                headers=headers,
            )
            response.raise_for_status()
            vectors.extend(item["embedding"] for item in response.json()["data"])
    return np.asarray(vectors, dtype=float)


def is_available() -> bool:
    """Cheap probe of whether the embedding endpoint is reachable.

    Returns:
        bool: True if a one-token embedding call succeeds, else False.
    """
    if not config.USE_EMBEDDINGS:
        return False
    try:
        return embed_texts(["ping"]).shape[0] == 1
    except Exception:  # noqa: BLE001 - any failure means "fall back to feature distance"
        return False


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    """L2-normalize each row so a dot product equals cosine similarity.

    Args:
        matrix (numpy.ndarray): An ``(n, d)`` array.

    Returns:
        numpy.ndarray: The row-normalized array (zero rows left as zeros).
    """
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class EmbeddingIndex:
    """A cosine-similarity index over application embeddings.

    Attributes:
        ids (list[str]): Application ids, row-aligned with ``matrix``.
        matrix (numpy.ndarray): L2-normalized ``(n, d)`` embedding matrix.
    """

    def __init__(self, ids: list[str], matrix: np.ndarray) -> None:
        """Store row-aligned ids and an L2-normalized embedding matrix.

        Args:
            ids (list[str]): Application ids.
            matrix (numpy.ndarray): The ``(n, d)`` embedding matrix (normalized on store).
        """
        self.ids = list(ids)
        self.matrix = _l2_normalize(matrix) if len(matrix) else matrix

    @classmethod
    def build(cls, ids: list[str], texts: list[str]) -> EmbeddingIndex:
        """Build an index by embedding the given texts.

        Args:
            ids (list[str]): Application ids.
            texts (list[str]): The text to embed for each id (row-aligned).

        Returns:
            EmbeddingIndex: The built index.
        """
        return cls(ids, embed_texts(texts))

    def query(self, text: str, k: int, exclude_id: str | None = None) -> list[tuple[str, float]]:
        """Return the k most cosine-similar application ids to a query text.

        Args:
            text (str): The query text (e.g. the target application's description).
            k (int): Number of neighbours to return.
            exclude_id (str | None): An application id to drop from the results (the query itself).

        Returns:
            list[tuple[str, float]]: ``(application_id, similarity)`` pairs, best first.
        """
        if not self.ids:
            return []
        query_vec = _l2_normalize(embed_texts([text]))[0]
        scores = self.matrix @ query_vec
        order = np.argsort(scores)[::-1]
        out: list[tuple[str, float]] = []
        for idx in order:
            app_id = self.ids[idx]
            if exclude_id is not None and app_id == exclude_id:
                continue
            out.append((app_id, float(scores[idx])))
            if len(out) >= k:
                break
        return out

    def save(self, path: Path = config.EMBEDDINGS_PARQUET) -> None:
        """Persist the index to parquet (one row per application id + its vector).

        Args:
            path: Destination parquet path; defaults to ``config.EMBEDDINGS_PARQUET``.

        Returns:
            None.
        """
        config.ensure_dirs()
        frame = pd.DataFrame({"application_id": self.ids, "embedding": list(self.matrix)})
        frame.to_parquet(path, index=False)

    @classmethod
    def load(cls, path: Path = config.EMBEDDINGS_PARQUET) -> EmbeddingIndex | None:
        """Load a cached index from parquet, if present.

        Args:
            path: Source parquet path; defaults to ``config.EMBEDDINGS_PARQUET``.

        Returns:
            EmbeddingIndex | None: The loaded index, or None if the cache is absent.
        """
        if not path.exists():
            return None
        frame = pd.read_parquet(path)
        matrix = (
            np.vstack(frame["embedding"].to_list())
            if len(frame)
            else np.empty((0, config.EMBEDDING_DIM))
        )
        return cls(frame["application_id"].tolist(), matrix)


def application_text(record: dict) -> str:
    """Compose the text to embed for an application.

    Builds a feature-derived descriptor (neighborhood, units, height, affordable share, retail,
    variances) so the indexed text lives in the *same* space as the query text built by
    ``retrieval._query_text`` from a Contract-1 application. The previous implementation read
    ``application_type``/``address``/``description`` columns that do not exist in this dataset's
    schema, so every row embedded the empty string and the index collapsed to one vector — making
    precedent retrieval return a fixed set regardless of the query. Any real prose fields present
    are appended so retrieval stays rich on datasets that do carry them.

    Args:
        record (dict): An application row (Contract-1 fields, optionally with prose columns).

    Returns:
        str: A compact descriptor string for embedding.
    """
    from vote_predictor.features import build_features

    feats = build_features(record)
    descriptor = (
        f"{feats.neighborhood} development, {feats.total_units} units, "
        f"{feats.height_m:.0f}m tall, {feats.affordable_share:.0%} affordable, "
        f"{'with' if feats.retail_flag else 'no'} retail, "
        f"{feats.requested_variances_count} variances"
    )
    prose = " ".join(
        str(record.get(field, "") or "") for field in ("application_type", "address", "description")
    ).strip()
    return f"{descriptor} {prose}".strip() if prose else descriptor


def build_application_index(apps: pd.DataFrame, save: bool = True) -> EmbeddingIndex:
    """Embed every application's text and build (optionally cache) the retrieval index.

    Args:
        apps (pandas.DataFrame): The application table (``application_id`` + text fields).
        save (bool): When True, persist the index to ``config.EMBEDDINGS_PARQUET``.

    Returns:
        EmbeddingIndex: The built index.
    """
    ids = apps["application_id"].astype(str).tolist()
    texts = [application_text(record) for record in apps.to_dict("records")]
    index = EmbeddingIndex.build(ids, texts)
    if save:
        index.save()
    return index
