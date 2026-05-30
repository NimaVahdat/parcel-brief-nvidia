# connector

## What this does

The integration layer. Imports the four backend components (`vote-predictor`, `opposition-generator`, `massing-generator`, `site-proforma`) and orchestrates them via LangGraph into a single Development Brief. Exposes the brief over HTTP for the UI.

The connector owns **no data**. It is pure orchestration.

## Contract

```
POST /analyze
Content-Type: application/json
Body:    { "parcel_id": str }
Returns: BriefResponse (see docs/CONTRACTS.md)
```

The `BriefResponse` Pydantic model in `src/connector/schemas/brief.py` is the source of truth between the connector and the UI.

## How to run

```bash
# from repo root — installs the workspace (including the four components)
uv sync

# start the API on :8000
uv run uvicorn connector.api.main:app --reload --port 8000

# smoke test
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"parcel_id": "543-dundas-w"}'
```

## How the LangGraph orchestration works

`src/connector/agents/graph.py` defines a `StateGraph` over `BriefState`. The graph runs:

```
        START
         │
    ┌────┴────┐
    ▼         ▼
 zoning   constraints    (parallel — both only need parcel_id)
    │         │
    └────┬────┘
         ▼
      massing             (depends on zoning + constraints)
         │
         ▼
     proforma             (depends on massing)
         │
    ┌────┴────┐
    ▼         ▼
 approvals  community     (parallel — both only need parcel + project)
    │         │
    └────┬────┘
         ▼
     principal            (synthesizes everything)
         │
         ▼
        END
```

Each agent is a thin wrapper that reads the relevant slice of state, calls one of the four component packages, and writes its result back to state.

## File map

| File | Purpose |
|---|---|
| `src/connector/__init__.py` | Package marker |
| `src/connector/api/main.py` | FastAPI app + CORS |
| `src/connector/api/routes/analyze.py` | `POST /analyze` |
| `src/connector/agents/state.py` | `BriefState` TypedDict |
| `src/connector/agents/graph.py` | LangGraph wiring with parallel edges |
| `src/connector/agents/zoning.py` | → `site_proforma.lookup` |
| `src/connector/agents/constraints.py` | → `site_proforma.lookup` (constraints slice) |
| `src/connector/agents/massing.py` | → `massing_generator.generate` |
| `src/connector/agents/proforma.py` | → `site_proforma.calculate` |
| `src/connector/agents/approvals.py` | → `vote_predictor.predict` |
| `src/connector/agents/community.py` | → `opposition_generator.generate` |
| `src/connector/agents/principal.py` | Synthesizer; writes `GoNoGo` |
| `src/connector/schemas/brief.py` | `BriefResponse` — THE FINAL CONTRACT |
| `tests/test_smoke.py` | End-to-end smoke test of the orchestrator |
