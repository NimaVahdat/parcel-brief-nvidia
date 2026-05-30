"""Offline tests for precedent aggregation: probability, per-councillor, swing."""

from vote_predictor.precedent import (
    application_to_text,
    approval_probability,
    per_councillor_estimates,
    swing_councillors,
)
from vote_predictor.retrieve import Retrieved
from vote_predictor.schemas import ApplicationFeatures
from vote_predictor.store import Precedent


def _r(outcome, score=1.0, votes=None) -> Retrieved:
    return Retrieved(
        Precedent(precedent_id="x", text="t", outcome=outcome, votes=votes or {}),
        score,
    )


def test_application_to_text_mentions_key_fields() -> None:
    app = ApplicationFeatures(
        parcel_id="p", height_m=42, total_units=84, affordable_units=0,
        retail_sqft=2400, use_mix={"residential": 1.0}, neighborhood="Trinity-Bellwoods",
    )
    text = application_to_text(app)
    assert "Trinity-Bellwoods" in text and "84 units" in text and "no affordable" in text


def test_approval_probability_weighted() -> None:
    prob, approved, total = approval_probability(
        [_r("approved"), _r("approved"), _r("approved"), _r("refused")]
    )
    assert total == 4 and approved == 3
    assert 0.7 <= prob <= 0.8


def test_per_councillor_uses_recorded_votes() -> None:
    retrieved = [
        _r("approved", votes={"alice": "yes"}),
        _r("approved", votes={"alice": "no"}),
        _r("refused", votes={"bob": "no"}),
    ]
    est = per_councillor_estimates(["alice", "bob", "carol"], 0.6, retrieved)
    assert est["alice"] == 0.5      # 1 yes / 2 votes
    assert est["bob"] == 0.0        # 0 yes / 1 vote
    assert 0.05 <= est["carol"] <= 0.95   # fallback spread around 0.6


def test_swing_councillors() -> None:
    assert swing_councillors({"a": 0.5, "b": 0.9, "c": 0.45}) == ["a", "c"]
