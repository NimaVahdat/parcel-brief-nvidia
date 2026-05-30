# parcel-brief

An AI co-developer for Toronto real estate. Pick a Toronto parcel, get a decision-grade Development Brief in a few minutes: legal building envelope, site constraints, 3D massing, financial pro-forma, predicted council vote, and predicted community opposition. The goal is to replace a four-to-eight-week, $150K–$300K consultant workflow with a single local-GPU stack.

## The Six Components

The project is organized as six independent components. Each one is a standalone sub-project with its own data ingestion and its own logic. The **connector** glues them together at the end.

| # | Component | What it does | Exports |
|---|---|---|---|
| 1 | `vote-predictor/` | Predicts how Toronto council will vote on a development application | `predict(application, councillors) → VotePrediction` |
| 2 | `opposition-generator/` | Generates community opposition letters in the voice of the actual neighborhood | `generate(project, neighborhood) → OppositionForecast` |
| 3 | `massing-generator/` | Generates 3D building massings that fit a zoning envelope | `generate(envelope) → MassingOutput` |
| 4 | `site-proforma/` | Looks up zoning + site constraints; runs the financial pro-forma | `lookup(parcel_id)`; `calculate(massing, site)` |
| 5 | `connector/` | Orchestrates the four into a Development Brief; serves the HTTP API | `POST /analyze {parcel_id} → BriefResponse` |
| 6 | `ui/` | Toronto map + brief viewer | Next.js app on `:3000` |

The five interface contracts live in `docs/CONTRACTS.md`. They are the only stable interfaces between components — everything else inside a component is the owner's call.

## Setup

```bash
git clone <repo>
cd parcel-brief

# Python workspace (installs all five backend components into a shared venv)
uv sync

# Optional shared infrastructure: Postgres + PostGIS + pgvector
docker compose up -d
```

Each component also has its own setup notes in its `README.md`.

## How to Demo Anything End-to-End

```bash
# 1. Connector (imports all four backend components, exposes the API)
uv run uvicorn connector.api.main:app --reload --port 8000

# 2. UI (separate terminal)
cd ui && npm install && npm run dev
# → open http://localhost:3000, click a Toronto parcel, see the brief

# 3. Any single component in isolation
uv run python -m vote_predictor.cli --demo
uv run python -m opposition_generator.cli --demo
uv run python -m massing_generator.cli --demo
uv run python -m site_proforma.cli --demo
```

The scaffold ships with every component returning mock data. The end-to-end flow works on day one. Each teammate replaces the inside of their component without touching anyone else.

## Working as a Team

- **Lock the contracts first.** Day 1 the team agrees on `docs/CONTRACTS.md` and commits it. Everything else flows from there.
- **Each component is yours.** Whatever data ingestion, library choices, and internal layout work for your piece. The only fixed thing is the contract you export.
- **Don't import across components.** Only the connector imports the others. Components talk through their contracts, not through each other's internals.
- **Don't commit `data/`.** Already in `.gitignore`. Local data dumps stay local.

## Docs

- `docs/PRD.md` — product requirements: what we're building and why
- `docs/CONTRACTS.md` — the five interface contracts (source of truth)
- `docs/DATA.md` — verified Toronto Open Data + TMMIS URLs, risk findings
- Per-component `README.md` — what each component does, its current state, and the next concrete tasks

## Stack

Python 3.12 (uv workspace) · FastAPI · LangGraph · Pydantic v2 · PyTorch · transformers · peft · xgboost · sentence-transformers · diffusers · Postgres + PostGIS + pgvector · Next.js 14 · TypeScript · react-leaflet · Tailwind

Built for NVIDIA Spark Hack Toronto, May 2026.
