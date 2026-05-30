"""POST /analyze — runs the LangGraph orchestrator and returns the brief."""

from fastapi import APIRouter, HTTPException

from connector.agents.graph import get_graph
from connector.schemas.brief import AnalyzeRequest, BriefResponse

router = APIRouter()


@router.post("/analyze", response_model=BriefResponse)
def analyze(req: AnalyzeRequest) -> BriefResponse:
    graph = get_graph()
    initial_state = {"parcel_id": req.parcel_id}
    final_state = graph.invoke(initial_state)

    try:
        return BriefResponse(
            parcel_id=req.parcel_id,
            site_fundamentals=final_state["site_fundamentals"],
            site_constraints=final_state["site_constraints"],
            design_options=final_state["design_options"],
            financial_model=final_state["financial_model"],
            approval_forecast=final_state["approval_forecast"],
            community_response=final_state["community_response"],
            recommendation=final_state["recommendation"],
        )
    except KeyError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Graph completed but state is missing field: {e}",
        ) from e
