"""Leave-one-out retrieval eval over the deputation corpus.

For each deputation, we hold it out, query retrieval with its own text, and check
whether the retrieved neighbours (a) come from the same neighbourhood and (b) share
its concerns. Reports neighborhood-hit@k and concern-overlap@k — a cheap, honest
signal of retrieval quality that we can quote ("validated against held-out data").

Run on the GB10 (needs Ollama + a built index):
    python -m eval.evaluate            # uses whatever load_corpus() returns
"""

from __future__ import annotations

import numpy as np

from opposition_generator.index.corpus import load_corpus
from opposition_generator.index.embed import embed_batch
from opposition_generator.index.retrieve import (
    mmr_select,
    reciprocal_rank_fusion,
    tokenize,
)


def evaluate(k: int = 5) -> dict:
    records = load_corpus()
    if len(records) < 3:
        raise SystemExit("corpus too small to evaluate")

    texts = [r["text"] for r in records]
    embeddings = np.array(embed_batch(texts), dtype=np.float32)

    neighborhood_hits = 0
    concern_overlaps: list[float] = []

    for i, query in enumerate(records):
        others = [j for j in range(len(records)) if j != i]
        ids = [str(j) for j in others]

        # dense ranking
        qv = embeddings[i] / (np.linalg.norm(embeddings[i]) + 1e-9)
        om = embeddings[others] / (
            np.linalg.norm(embeddings[others], axis=1, keepdims=True) + 1e-9
        )
        dense_order = [ids[x] for x in np.argsort(-(om @ qv))]

        # lexical ranking
        try:
            from rank_bm25 import BM25Okapi

            bm25 = BM25Okapi([tokenize(records[j]["text"]) for j in others])
            scores = bm25.get_scores(tokenize(query["text"]))
            lex_order = [ids[x] for x in np.argsort(-scores)]
            fused = reciprocal_rank_fusion([dense_order, lex_order])
        except ImportError:
            fused = reciprocal_rank_fusion([dense_order])

        pool = [i2 for i2, _ in sorted(fused.items(), key=lambda kv: -kv[1])][: k * 3]
        pool_emb = embeddings[[int(p) for p in pool]]
        top = mmr_select(pool, pool_emb, fused, k)
        top_idx = [int(p) for p in top]

        if any(records[j]["neighborhood"] == query["neighborhood"] for j in top_idx):
            neighborhood_hits += 1

        q_concerns = set(query["concerns"])
        if q_concerns:
            overlap = [
                len(q_concerns & set(records[j]["concerns"])) / len(q_concerns)
                for j in top_idx
            ]
            concern_overlaps.append(max(overlap) if overlap else 0.0)

    n = len(records)
    metrics = {
        "corpus_size": n,
        "k": k,
        f"neighborhood_hit@{k}": round(neighborhood_hits / n, 3),
        f"concern_overlap@{k}": round(
            sum(concern_overlaps) / len(concern_overlaps), 3
        )
        if concern_overlaps
        else None,
    }
    return metrics


if __name__ == "__main__":
    import json

    print(json.dumps(evaluate(), indent=2))
