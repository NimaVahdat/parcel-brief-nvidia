"""Unit tests for the deterministic aggregation math."""

import pytest
from vote_predictor.aggregate import poisson_binomial_majority, swing_councillors


@pytest.mark.parametrize(
    "probs,expected",
    [([1.0, 1.0, 1.0], 1.0), ([0.0, 0.0, 0.0], 0.0), ([0.5, 0.5, 0.5], 0.5), ([1.0, 0.0], 0.0)],
)
def test_poisson_binomial_majority(probs, expected):
    """The Poisson-binomial majority probability matches hand-computed values."""
    assert poisson_binomial_majority(probs) == pytest.approx(expected)


def test_swing_councillors_picks_near_half():
    """Only councillors within the swing band of 0.5 are flagged, most uncertain first."""
    per = {"a": 0.51, "b": 0.95, "c": 0.46}
    assert swing_councillors(per) == ["a", "c"]
