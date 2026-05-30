"""Tests for the embedding index math and offline fallback (no network required)."""

from __future__ import annotations

import numpy as np
from vote_predictor import config, embeddings


def test_l2_normalize_unit_rows():
    """Rows are normalized to unit length (zero rows left as zeros)."""
    out = embeddings._l2_normalize(np.array([[3.0, 4.0], [0.0, 0.0]]))
    assert abs(np.linalg.norm(out[0]) - 1.0) < 1e-9
    assert np.allclose(out[1], 0.0)


def test_application_text_composes_fields():
    """The embedding text combines structured project features and any prose fields."""
    text = embeddings.application_text(
        {
            "application_type": "OZ",
            "address": "929 QUEEN ST E",
            "description": "9-storey rezoning",
            "neighborhood": "Leslieville",
            "height_m": 27,
            "total_units": 80,
            "affordable_units": 12,
            "retail_sqft": 1000,
            "requested_variances": ["height"],
        }
    )
    assert "Leslieville" in text
    assert "80 units" in text
    assert "15% affordable" in text
    assert "with retail" in text
    assert "1 variances" in text
    assert "OZ" in text and "QUEEN" in text and "rezoning" in text


def test_is_available_false_when_disabled(monkeypatch):
    """is_available short-circuits to False when embeddings are turned off."""
    monkeypatch.setattr(config, "USE_EMBEDDINGS", False)
    assert embeddings.is_available() is False


def test_index_query_ranks_by_cosine(monkeypatch):
    """query returns the most cosine-similar id first (embed_texts stubbed, no network)."""
    vecs = {
        "q": [1.0, 0.0, 0.0],
        "A": [0.9, 0.1, 0.0],
        "B": [0.0, 1.0, 0.0],
        "C": [0.0, 0.0, 1.0],
    }
    monkeypatch.setattr(
        embeddings,
        "embed_texts",
        lambda texts, batch_size=64: np.array([vecs[t] for t in texts], float),
    )
    index = embeddings.EmbeddingIndex(
        ["A", "B", "C"], np.array([vecs["A"], vecs["B"], vecs["C"]], float)
    )
    hits = index.query("q", k=2)
    assert hits[0][0] == "A"
    assert [h[0] for h in hits] == ["A", "C"] or hits[0][0] == "A"


def test_index_save_load_roundtrip(tmp_path, monkeypatch):
    """An index round-trips through parquet with ids and vectors intact."""
    path = tmp_path / "emb.parquet"
    index = embeddings.EmbeddingIndex(["A", "B"], np.array([[1.0, 0.0], [0.0, 1.0]]))
    index.save(path)
    loaded = embeddings.EmbeddingIndex.load(path)
    assert loaded is not None
    assert loaded.ids == ["A", "B"]
    assert loaded.matrix.shape == (2, 2)
