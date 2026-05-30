"""End-to-end smoke test: graph runs and returns a complete BriefResponse."""

from fastapi.testclient import TestClient

from connector.agents.graph import get_graph
from connector.api.main import app
from connector.schemas.brief import BriefResponse


def test_graph_returns_full_state() -> None:
    graph = get_graph()
    state = graph.invoke({"parcel_id": "test-123"})
    assert "site_fundamentals" in state
    assert "design_options" in state
    assert "financial_model" in state
    assert "approval_forecast" in state
    assert "community_response" in state
    assert "recommendation" in state


def test_analyze_endpoint_returns_brief() -> None:
    client = TestClient(app)
    response = client.post("/analyze", json={"parcel_id": "543-dundas-w"})
    assert response.status_code == 200
    brief = BriefResponse.model_validate(response.json())
    assert brief.parcel_id == "543-dundas-w"
    assert brief.recommendation.recommendation in {"buy", "pass", "conditional"}
