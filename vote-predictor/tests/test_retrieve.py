"""Offline tests for the pure ranking logic: tokenize, RRF, MMR."""

import numpy as np

from vote_predictor.retrieve import mmr_select, reciprocal_rank_fusion, tokenize


def test_tokenize() -> None:
    assert tokenize("42 m, Zoning By-law!") == ["42", "m", "zoning", "by", "law"]


def test_rrf_rewards_consensus() -> None:
    rankings = [["a", "b", "c"], ["b", "c", "a"]]
    fused = reciprocal_rank_fusion(rankings)
    assert max(fused, key=fused.get) == "b"
    assert fused["b"] > fused["a"] > fused["c"]


def test_mmr_avoids_duplicates() -> None:
    ids = ["a", "b", "c"]
    emb = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    chosen = mmr_select(ids, emb, {"a": 1.0, "b": 0.9, "c": 0.5}, k=2, lambda_=0.5)
    assert chosen[0] == "a"
    assert chosen[1] == "c"
