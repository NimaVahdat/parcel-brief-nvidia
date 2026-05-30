"""Hybrid retrieval: HyDE -> (dense + BM25) -> RRF -> MMR -> top-k.

Why hybrid:
  * dense (embeddings) captures "situations like this" semantically;
  * BM25 (lexical) captures exact tokens dense misses — street names, a specific
    residents-association name, "laneway", a councillor's name;
  * RRF fuses the two rank lists without tuning score scales;
  * MMR diversifies the winners so the top-k isn't k near-duplicate letters about
    one past project (which would skew the forecast).
  * HyDE turns the short structured project into a hypothetical deputation before
    the dense search, so we match letter-to-letter instead of spec-to-letter.

Every external call (LLM for HyDE, embeddings) degrades gracefully: if HyDE fails
we embed the project text directly; if embeddings fail we fall back to BM25-only;
if BM25 is unavailable we fall back to dense-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from opposition_generator import config
from opposition_generator.index.embed import EmbeddingError, embed_text
from opposition_generator.index.store import Deputation, get_store

# neighborhood is "thin" if it has fewer than this many letters; broaden city-wide.
_MIN_NEIGHBORHOOD_CANDIDATES = 4
_RRF_K0 = 60
_MMR_LAMBDA = 0.7
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class Retrieved:
    deputation: Deputation
    score: float
    same_neighborhood: bool


# --------------------------------------------------------------------------- #
# Pure ranking helpers (no I/O — unit-tested offline)
# --------------------------------------------------------------------------- #
def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def reciprocal_rank_fusion(
    rankings: list[list[str]], k0: int = _RRF_K0
) -> dict[str, float]:
    """Fuse several ranked id-lists into one id->score map. Rank is 1-based."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k0 + rank)
    return scores


def _cosine_matrix(query: np.ndarray, mat: np.ndarray) -> np.ndarray:
    qn = query / (np.linalg.norm(query) + 1e-9)
    mn = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
    return mn @ qn


def mmr_select(
    ids: list[str],
    embeddings: np.ndarray,
    relevance: dict[str, float],
    k: int,
    lambda_: float = _MMR_LAMBDA,
) -> list[str]:
    """Maximal Marginal Relevance selection over candidates.

    Balances relevance (RRF score) against novelty (1 - max sim to already chosen).
    """
    if not ids:
        return []
    idx = {dep_id: i for i, dep_id in enumerate(ids)}
    rel = np.array([relevance.get(i, 0.0) for i in ids])
    if rel.max() > 0:
        rel = rel / rel.max()
    norm = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-9)
    sim = norm @ norm.T

    selected: list[str] = []
    remaining = set(ids)
    while remaining and len(selected) < k:
        best_id, best_val = None, -np.inf
        for cand in remaining:
            ci = idx[cand]
            novelty = 0.0 if not selected else max(sim[ci][idx[s]] for s in selected)
            val = lambda_ * rel[ci] - (1 - lambda_) * novelty
            if val > best_val:
                best_val, best_id = val, cand
        selected.append(best_id)
        remaining.discard(best_id)
    return selected


# --------------------------------------------------------------------------- #
# HyDE
# --------------------------------------------------------------------------- #
def hyde_expand(project_text: str, neighborhood: str) -> str:
    """Draft a hypothetical deputation for dense matching. Falls back to the input."""
    from opposition_generator.llm import LLMError, chat

    prompt = (
        "Write a short (4-6 sentence) community deputation letter OPPOSING the "
        f"following development in the {neighborhood} neighbourhood of Toronto. "
        "Write in the voice of a concerned local resident. Name concrete concerns "
        "(shadow, traffic, height, character, affordability, etc.) that such a "
        f"project would raise.\n\nProject:\n{project_text}"
    )
    try:
        return chat(prompt, temperature=0.7)
    except LLMError:
        return project_text


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def retrieve(
    project_text: str,
    neighborhood: str,
    k: int | None = None,
    *,
    use_hyde: bool = True,
) -> list[Retrieved]:
    """Return the top-k most relevant past deputations for a project.

    Filters to `neighborhood` first; broadens city-wide if that pool is thin.
    """
    k = k or config.DEFAULT_TOP_K
    store = get_store()

    local = store.fetch(neighborhood)
    if len(local) >= _MIN_NEIGHBORHOOD_CANDIDATES:
        candidates = local
    else:
        # broaden: same-neighborhood letters still get a relevance boost downstream
        candidates = store.fetch(None)
    if not candidates:
        return []

    ids = [c.deputation_id for c in candidates]
    by_id = {c.deputation_id: c for c in candidates}
    same_hood = {c.deputation_id: (c.neighborhood == neighborhood) for c in candidates}

    rankings: list[list[str]] = []

    # --- dense leg (HyDE -> embed -> cosine) ---
    dense_embeddings: np.ndarray | None = None
    try:
        query_text = hyde_expand(project_text, neighborhood) if use_hyde else project_text
        qvec = np.array(embed_text(query_text), dtype=np.float32)
        mat = np.array([c.embedding for c in candidates], dtype=np.float32)
        dense_scores = _cosine_matrix(qvec, mat)
        dense_order = [ids[i] for i in np.argsort(-dense_scores)]
        rankings.append(dense_order)
        dense_embeddings = mat
    except (EmbeddingError, ValueError):
        pass  # embeddings unavailable -> rely on lexical

    # --- lexical leg (BM25) ---
    try:
        from rank_bm25 import BM25Okapi

        corpus_tokens = [tokenize(by_id[i].text) for i in ids]
        bm25 = BM25Okapi(corpus_tokens)
        query_tokens = tokenize(f"{neighborhood} {project_text}")
        bm25_scores = bm25.get_scores(query_tokens)
        bm25_order = [ids[i] for i in np.argsort(-bm25_scores)]
        rankings.append(bm25_order)
    except ImportError:
        pass  # rank_bm25 not installed -> dense-only

    if not rankings:
        # No ranker available at all (no embeddings, no bm25): same-neighborhood first.
        ordered = sorted(ids, key=lambda i: (not same_hood[i],))
        return [Retrieved(by_id[i], 0.0, same_hood[i]) for i in ordered[:k]]

    # --- fuse + diversify ---
    fused = reciprocal_rank_fusion(rankings)
    # nudge same-neighborhood letters up when we had to broaden city-wide
    for i in ids:
        if same_hood[i]:
            fused[i] = fused.get(i, 0.0) * 1.15

    if dense_embeddings is not None:
        pool_size = min(len(ids), max(k * 3, 12))
        pool = [i for i, _ in sorted(fused.items(), key=lambda kv: -kv[1])][:pool_size]
        pool_emb = np.array([by_id[i].embedding for i in pool], dtype=np.float32)
        chosen = mmr_select(pool, pool_emb, fused, k)
    else:
        chosen = [i for i, _ in sorted(fused.items(), key=lambda kv: -kv[1])][:k]

    return [Retrieved(by_id[i], fused.get(i, 0.0), same_hood[i]) for i in chosen]
