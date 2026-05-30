# CLAUDE.md — Project Memory for Claude Code

You are working in `parcel-brief`, a Toronto real estate pre-acquisition analysis system. Read this file first whenever you open the repo.

## What the project does

A user clicks a Toronto parcel on a map and gets a Development Brief in a few minutes: legal building envelope, site constraints, 3D massing, financial pro-forma, predicted council vote, and predicted community opposition. The brief is decision-grade for real estate developers screening sites for acquisition — replacing a 4–8 week, $150K–$300K consultant workflow.

## Architecture: Six Components

The repo is organized as six independent components, each a standalone sub-project with its own data ingestion and logic. Components communicate only through the five contracts in `docs/CONTRACTS.md`.

| Component | Folder | Contract |
|---|---|---|
| Vote Predictor | `vote-predictor/` | `predict(application, councillors) → VotePrediction` |
| Opposition Generator | `opposition-generator/` | `generate(project, neighborhood) → OppositionForecast` |
| Massing Generator | `massing-generator/` | `generate(envelope) → MassingOutput` |
| Site & Pro-Forma | `site-proforma/` | `lookup(parcel_id) → SiteData`; `calculate(massing, site) → FinancialModel` |
| Connector | `connector/` | `POST /analyze {parcel_id} → BriefResponse` (LangGraph orchestrator + FastAPI) |
| UI | `ui/` | Next.js 14 app — Toronto map + brief viewer |

The connector imports the four backend components as Python packages (uv workspace) and orchestrates them with LangGraph. The UI hits the connector's HTTP API.

## Current state

Every component ships as a working stub: imports resolve, CLIs run, services start, end-to-end pipeline returns a mock brief. No real models trained yet, no real data ingested. The team replaces stubs incrementally; the contracts stay stable.

When you make changes, check each component's `README.md` for what's stubbed vs. what's real at the time you read this.

## Stack

- **Python** 3.12 with `uv` (workspace monorepo — each backend component is a workspace member)
- **API**: FastAPI
- **Orchestration**: LangGraph (StateGraph with parallel edges; `BriefState` TypedDict in `connector/src/connector/agents/state.py`)
- **Validation**: Pydantic v2 — Pydantic models for every contract, re-declared per component
- **ML**: PyTorch, transformers, peft (LoRA), xgboost, sentence-transformers, diffusers
- **Database** (optional shared): Postgres 16 + PostGIS + pgvector via `docker-compose.yml`. Components that need it use it; others use local file storage.
- **Frontend**: Next.js 14 (app router), TypeScript, react-leaflet, Tailwind

## Conventions

- **uv** for Python. `uv sync` at repo root installs everything.
- **ruff** for formatting/linting Python (`uv run ruff format .` and `uv run ruff check .`).
- **prettier** for TypeScript in `ui/`.
- **Pydantic v2** for all data shapes. Use `model_dump()` not `.dict()`.
- **LangGraph**: agents read/write the shared `BriefState`; each agent owns one field of the state.
- **Per-component independence**: components never import each other's internals. Only the connector imports the four components, and only through their `__init__.py` re-exports.

## Don't do

- Don't commit `data/` directories — they're gitignored. Local data dumps stay local.
- Don't break a contract in `docs/CONTRACTS.md` without team agreement. The contracts are the only stable interface.
- Don't import across components (except connector → others). If component A needs something from component B, change the contract or move the logic.
- Don't add a new top-level folder without team discussion.
- Don't `git push --force` to the main branch.

## Datasets

All verified Toronto Open Data, TMMIS, CMHC, and StatsCan URLs are in `docs/DATA.md`. Both data risks identified during the audit are green:

- TMMIS exposes per-councillor committee votes via the Voting Record CSV report (only when a recorded vote was called; routine for contentious development items).
- Deputation PDFs are text-extractable in the verified samples. Expect ~10–20% to be image-only and need OCR fallback.

TMMIS is behind Akamai and 403s plain HTTP — the scraper needs a headless browser (Playwright).

## Hackathon context

Built for NVIDIA Spark Hack Toronto, May 2026. Hardware: ASUS GX10 with NVIDIA GB10. Antler is the VC co-host — the pitch needs to feel like a real company, not a weekend toy. Track: Economic Systems (primary), Urban Operations (crossover).

## When in doubt

Read `docs/PRD.md` for what we're building. Read `docs/CONTRACTS.md` for how the components fit together. Read the component's own `README.md` for what it does and what's stubbed.
