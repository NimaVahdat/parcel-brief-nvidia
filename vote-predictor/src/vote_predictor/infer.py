"""predict() — the contract function. Stub returns mock data until trained model lands."""

from vote_predictor.schemas import ApplicationFeatures, Lever, VotePrediction

# TODO: load trained XGBoost model + LLM wrapper here once train.py is implemented.
# _model = joblib.load(Path(__file__).parent.parent.parent / "data" / "model.joblib")


def predict(application: ApplicationFeatures, councillors: list[str]) -> VotePrediction:
    """Predict how Toronto council will vote on a development application.

    Mock implementation. Replace with: feature extraction → XGBoost predict_proba →
    per-councillor adjustment using councillor history → LLM counterfactual generation.
    """
    base_probability = 0.5
    if application.affordable_units >= 12:
        base_probability += 0.2
    if application.height_m > 30:
        base_probability -= 0.1
    base_probability = max(0.05, min(0.95, base_probability))

    per_councillor = {c: max(0.1, min(0.9, base_probability + 0.05)) for c in councillors}
    swing = [c for c, p in per_councillor.items() if 0.35 <= p <= 0.65]

    levers = [
        Lever(change="add 12 affordable units", delta_probability=0.16),
        Lever(change="add 600 sqft community room", delta_probability=0.08),
        Lever(change="reduce height by 2 stories", delta_probability=0.05),
    ]

    return VotePrediction(
        approval_probability=base_probability,
        per_councillor=per_councillor,
        swing_councillors=swing,
        levers=levers,
    )
