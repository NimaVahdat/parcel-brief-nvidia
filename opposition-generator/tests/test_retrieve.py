"""Offline tests for the pure ranking logic: tokenize, RRF, MMR."""

import numpy as np

from opposition_generator.index.retrieve import (
    mmr_select,
    reciprocal_rank_fusion,
    tokenize,
)


def test_tokenize_lowercases_and_splits() -> None:
    assert tokenize("Trinity-Bellwoods Park, 89 Niagara St.") == [
        "trinity",
        "bellwoods",
        "park",
        "89",
        "niagara",
        "st",
    ]


def test_rrf_rewards_consensus() -> None:
    # "b" ranks 2nd then 1st; "a" ranks 1st then last. b's consensus wins.
    rankings = [["a", "b", "c"], ["b", "c", "a"]]
    fused = reciprocal_rank_fusion(rankings)
    assert max(fused, key=fused.get) == "b"
    assert fused["b"] > fused["a"] > fused["c"]


def test_rrf_single_ranking_preserves_order() -> None:
    fused = reciprocal_rank_fusion([["x", "y", "z"]])
    assert fused["x"] > fused["y"] > fused["z"]


def test_mmr_avoids_near_duplicates() -> None:
    ids = ["a", "b", "c"]
    # a and b are identical; c is orthogonal. With both a,b relevant, MMR should
    # pick one of {a,b} then prefer the novel c over the duplicate.
    emb = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    relevance = {"a": 1.0, "b": 0.9, "c": 0.5}
    chosen = mmr_select(ids, emb, relevance, k=2, lambda_=0.5)
    assert chosen[0] == "a"
    assert chosen[1] == "c"  # novelty beats the near-duplicate "b"
