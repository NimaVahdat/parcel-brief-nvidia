"""Tests for the FastAPI service: the additive agent_trace field and input validation."""

from __future__ import annotations

from fastapi.testclient import TestClient

_BODY = {
    "parcel_id": "T-1",
    "height_m": 40.0,
    "total_units": 100,
    "affordable_units": 12,
    "retail_sqft": 0.0,
    "use_mix": {"residential": 1.0},
    "neighborhood": "Test",
    "requested_variances": ["height"],
    "councillors": ["a", "b", "c"],
}


def _client(monkeypatch):
    """Build a TestClient with the LLM forced off (deterministic, offline)."""
    from vote_predictor import config, infer

    monkeypatch.setattr(config, "USE_LLM", False)
    infer._agent.cache_clear()
    from vote_predictor.service import app

    return TestClient(app)


def test_predict_returns_contract_fields_plus_additive_trace(monkeypatch):
    """The response carries Contract-1 fields and the additive agent_trace."""
    client = _client(monkeypatch)
    resp = client.post("/predict", json=_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert all(
        k in body for k in ("approval_probability", "per_councillor", "swing_councillors", "levers")
    )
    assert "agent_trace" in body and body["agent_trace"] is not None
    assert body["agent_trace"]["mode"] in {"panel", "fallback"}


def test_empty_councillors_is_rejected(monkeypatch):
    """An empty councillors list fails validation (422), not a meaningless 200."""
    client = _client(monkeypatch)
    resp = client.post("/predict", json={**_BODY, "councillors": []})
    assert resp.status_code == 422


def test_health(monkeypatch):
    """The health endpoint reports ok."""
    client = _client(monkeypatch)
    assert client.get("/health").json() == {"status": "ok"}
