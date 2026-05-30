"""Unit tests for the agent's offline fallback path (no LLM endpoint required)."""

from vote_predictor.agent import VotePredictorAgent
from vote_predictor.schemas import VotePrediction

APPLICATION = {
    "parcel_id": "T-1",
    "height_m": 40.0,
    "total_units": 100,
    "affordable_units": 10,
    "retail_sqft": 0.0,
    "use_mix": {"residential": 1.0},
    "neighborhood": "Test",
    "requested_variances": ["height"],
}


def test_fallback_predict_returns_valid_prediction():
    """With no profiles and the LLM off, the agent still returns a valid prediction."""
    agent = VotePredictorAgent(profiles={}, use_llm=False)
    pred = agent.predict(APPLICATION, ["a", "b", "c"], "unknown")
    assert isinstance(pred, VotePrediction)
    assert 0.0 <= pred.approval_probability <= 1.0
    assert set(pred.per_councillor) == {"a", "b", "c"}
    assert all(0.0 <= p <= 1.0 for p in pred.per_councillor.values())
    assert pred.levers, "expected at least one lever"


def _grounded_profiles(ids: list[str]) -> dict[str, dict]:
    """Build minimal grounded profiles so the Skeptic accepts (does not abstain) on these ids."""
    return {
        c: {
            "councillor_id": c,
            "committee": "toronto-east-york",
            "n_votes": 20,
            "yes_rate": 0.5,
            "propensity_logit": 0.0,
            "lean": "swing",
        }
        for c in ids
    }


def test_staff_recommendation_is_monotonic():
    """For grounded councillors, staff approval yields a higher approval probability than refusal."""
    agent = VotePredictorAgent(profiles=_grounded_profiles(["a", "b", "c"]), use_llm=False)
    approve = agent.predict(APPLICATION, ["a", "b", "c"], "approve").approval_probability
    refuse = agent.predict(APPLICATION, ["a", "b", "c"], "refuse").approval_probability
    assert approve > refuse


def test_ungrounded_councillor_abstains_to_prior_not_fabricated():
    """A councillor with no record/precedent abstains to a prior and is flagged (D3 fix)."""
    agent = VotePredictorAgent(profiles={}, use_llm=False)
    _, trace = agent.predict_with_trace(APPLICATION, ["nobody"], "approve")
    reasoning = trace.councillors[0]
    assert reasoning.grounded is False
    assert reasoning.basis == "prior"
    assert reasoning.skeptic_verdict in {"forced_abstain", "rejected_uncited"}
    assert trace.n_abstained == 1
