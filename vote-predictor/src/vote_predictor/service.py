"""Optional standalone FastAPI service. Lets you demo this component in isolation."""

from fastapi import FastAPI

from vote_predictor.infer import predict
from vote_predictor.schemas import ApplicationFeatures, VotePrediction

app = FastAPI(title="vote-predictor", version="0.0.1")


class PredictRequest(ApplicationFeatures):
    councillors: list[str]


@app.post("/predict", response_model=VotePrediction)
def predict_endpoint(req: PredictRequest) -> VotePrediction:
    application = ApplicationFeatures(
        parcel_id=req.parcel_id,
        height_m=req.height_m,
        total_units=req.total_units,
        affordable_units=req.affordable_units,
        retail_sqft=req.retail_sqft,
        use_mix=req.use_mix,
        neighborhood=req.neighborhood,
        requested_variances=req.requested_variances,
    )
    return predict(application, req.councillors)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
