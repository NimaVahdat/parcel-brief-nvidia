"""Hybrid retrieval over precedents: dense + BM25 -> RRF -> MMR -> top-k.

No HyDE here (unlike opposition): the query is already a structured application
descriptor, and levers re-run retrieval many times, so we keep it LLM-free and fast.
Degrades gracefully — embeddings down -> BM25-only; rank_bm25 missing -> dense-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from vote_predictor import config
from vote_predictor.embed import EmbeddingError, embed_text
from vote_predictor.store import Precedent, get_store

_RRF_K0 = 60
_MMR_LAMBDA = 0.7
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class Retrieved:
    precedent: Precedent
    score: float


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def reciprocal_rank_fusion(rankings: list[list[str]], k0: int = _RRF_K0) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k0 + rank)
    return scores


def _cosine(query: np.ndarray, mat: np.ndarray) -> np.ndarray:
    qn = query / (np.linalg.norm(query) + 1e-9)
    mn = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
    return mn @ qn


def mmr_select(ids, embeddings, relevance, k, lambda_=_MMR_LAMBDA):
    if not ids:
        return []
    idx = {i: n for n, i in enumerate(ids)}
    rel = np.array([relevance.get(i, 0.0) for i in ids])
    if rel.max() > 0:
        rel = rel / rel.max()
    norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9)
    sim = norm @ norm.T
    selected, remaining = [], set(ids)
    while remaining and len(selected) < k:
        best_id, best = None, -np.inf
        for cand in remaining:
            ci = idx[cand]
            novelty = 0.0 if not selected else max(sim[ci][idx[s]] for s in selected)
            val = lambda_ * rel[ci] - (1 - lambda_) * novelty
            if val > best:
                best, best_id = val, cand
        selected.append(best_id)
        remaining.discard(best_id)
    return selected


def retrieve(
    query_text: str,
    k: int | None = None,
    *,
    candidates: list[Precedent] | None = None,
) -> list[Retrieved]:
    """Return the top-k most similar precedents to a query application.

    `candidates` lets the eval harness pass a held-out training set; otherwise we
    pull the full corpus from the store.
    """
    k = k or config.DEFAULT_TOP_K
    if candidates is None:
        candidates = get_store().fetch()
    if not candidates:
        return []

    ids = [c.precedent_id for c in candidates]
    by_id = {c.precedent_id: c for c in candidates}
    rankings: list[list[str]] = []
    dense_mat: np.ndarray | None = None

    try:
        qvec = np.array(embed_text(query_text), dtype=np.float32)
        mat = np.array([c.embedding for c in candidates], dtype=np.float32)
        dense = _cosine(qvec, mat)
        rankings.append([ids[i] for i in np.argsort(-dense)])
        dense_mat = mat
    except (EmbeddingError, ValueError):
        pass

    try:
        from rank_bm25 import BM25Okapi

        bm25 = BM25Okapi([tokenize(by_id[i].text) for i in ids])
        scores = bm25.get_scores(tokenize(query_text))
        rankings.append([ids[i] for i in np.argsort(-scores)])
    except ImportError:
        pass

    if not rankings:
        return [Retrieved(by_id[i], 0.0) for i in ids[:k]]

    fused = reciprocal_rank_fusion(rankings)
    if dense_mat is not None:
        pool = [i for i, _ in sorted(fused.items(), key=lambda kv: -kv[1])][: max(k * 3, 18)]
        pool_emb = np.array([by_id[i].embedding for i in pool], dtype=np.float32)
        chosen = mmr_select(pool, pool_emb, fused, k)
    else:
        chosen = [i for i, _ in sorted(fused.items(), key=lambda kv: -kv[1])][:k]
    return [Retrieved(by_id[i], fused.get(i, 0.0)) for i in chosen]
