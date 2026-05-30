"""Approvals agent — calls vote_predictor.predict."""

from vote_predictor import predict
from vote_predictor.schemas import ApplicationFeatures

from connector.agents.state import BriefState
from connector.geo import resolve_context
from connector.schemas.brief import VotePrediction


def approvals_agent(state: BriefState) -> BriefState:
    envelope = state["site_fundamentals"]
    massing = state["design_options"].options[0]
    ctx = resolve_context(state["parcel_id"])

    application = ApplicationFeatures(
        parcel_id=envelope.parcel_id,
        height_m=massing.height_m,
        total_units=sum(massing.unit_mix.values()),
        affordable_units=massing.affordable_units,
        retail_sqft=massing.retail_sqft,
        use_mix={"residential": 0.85, "retail": 0.15},
        neighborhood=ctx["neighbourhood"],
    )

    prediction = predict(application, ctx["councillors"])
    return {"approval_forecast": VotePrediction.model_validate(prediction.model_dump())}
