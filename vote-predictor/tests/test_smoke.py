"""Smoke test: the contract function runs and returns the expected shape."""

from vote_predictor import predict
from vote_predictor.schemas import ApplicationFeatures, VotePrediction


def test_predict_returns_vote_prediction() -> None:
    application = ApplicationFeatures(
        parcel_id="test",
        height_m=30.0,
        total_units=50,
        affordable_units=10,
        retail_sqft=1000,
        use_mix={"residential": 1.0},
        neighborhood="Test-Neighborhood",
    )
    result = predict(application, councillors=["a", "b", "c"])
    assert isinstance(result, VotePrediction)
    assert 0 <= result.approval_probability <= 1
    assert len(result.per_councillor) == 3
    assert len(result.levers) > 0
