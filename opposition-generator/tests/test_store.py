"""Offline test for the SQLite store: upsert/fetch roundtrip + neighborhood filter."""

from opposition_generator.index.store import Deputation, LocalVectorStore


def _store(tmp_path):
    return LocalVectorStore(path=tmp_path / "t.sqlite3", dim=3)


def test_upsert_and_fetch_roundtrip(tmp_path) -> None:
    store = _store(tmp_path)
    store.reset()
    store.upsert_many(
        [
            Deputation("a", "Annex", "letter a", ["shadow"], ["ARA"], "midrise", [0.1, 0.2, 0.3]),
            Deputation("b", "Rosedale", "letter b", ["heritage"], [], "lowrise", [0.4, 0.5, 0.6]),
        ]
    )
    assert store.count() == 2
    fetched = {d.deputation_id: d for d in store.fetch()}
    assert fetched["a"].concerns == ["shadow"]
    assert fetched["a"].groups == ["ARA"]
    assert len(fetched["a"].embedding) == 3
    assert abs(fetched["b"].embedding[0] - 0.4) < 1e-5


def test_neighborhood_filter(tmp_path) -> None:
    store = _store(tmp_path)
    store.reset()
    store.upsert_many(
        [
            Deputation("a", "Annex", "x", [], [], "", [0.0, 0.0, 0.0]),
            Deputation("b", "Rosedale", "y", [], [], "", [0.0, 0.0, 0.0]),
        ]
    )
    annex = store.fetch("Annex")
    assert [d.deputation_id for d in annex] == ["a"]


def test_upsert_is_idempotent(tmp_path) -> None:
    store = _store(tmp_path)
    store.reset()
    dep = Deputation("a", "Annex", "v1", [], [], "", [1.0, 0.0, 0.0])
    store.upsert_many([dep])
    store.upsert_many([Deputation("a", "Annex", "v2", [], [], "", [0.0, 1.0, 0.0])])
    rows = store.fetch()
    assert len(rows) == 1
    assert rows[0].text == "v2"
