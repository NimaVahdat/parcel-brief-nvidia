# parcel-brief

**An AI co-developer for Toronto real estate that runs entirely on a single NVIDIA GB10.**

Click a Toronto parcel on the map and get a decision-grade **Development Brief** in a few minutes: the legal building envelope, site constraints, an interactive 3D massing, a financial pro-forma, a predicted council vote, and a community-opposition forecast — every section grounded in real public data, not a generic model's guesses. It compresses a four-to-eight-week, **$150K–$300K** pre-acquisition consultant workflow into one **local-GPU** stack with **no cloud LLM and no per-token bill**.

> Built for the **NVIDIA Spark Hack Series** on an **ASUS GX10 / NVIDIA GB10** (128 GB unified memory). The whole reasoning stack — including a **120B-parameter** model — runs on-device.

## What it does, end to end

A click on a parcel fans out through a LangGraph pipeline and streams back a brief:

1. **Site & zoning** — resolves the legal envelope (height, FSI, setbacks, permitted uses) and constraints (heritage, fire-station distance, transit, tree canopy) from Toronto Open Data.
2. **3D massing** — builds an interactive retail-base → podium → setback-tower massing that fits the envelope, rendered instantly (deterministic, no LLM).
3. **Pro-forma** — construction cost, rent, sale, debt service, 5/10-yr IRR with sensitivities.
4. **Council vote** — a grounded multi-agent panel predicts the approval probability from Toronto's real application-outcome record.
5. **Community opposition** — expected letter volume, ranked concerns, organized groups, and sample deputation letters written in the neighbourhood's actual voice.
6. **Recommendation** — a buy / conditional / pass call with a 0–100 developability score and the dominant sensitivities.

The user can also adjust the building (height / units / affordable / retail) and re-run — the pro-forma, vote, opposition, and recommendation all re-evaluate *their* building.

## Grounded in real data

Nothing here is mocked — each section is backed by ingested public data:

- **Zoning & site** (`site-proforma`) — Toronto Open Data: zoning by-law areas + height overlays, property boundaries, heritage register, fire-station locations, transit stops (shapely point-in-polygon over real GeoJSON).
- **Community opposition** (`opposition-generator`) — hybrid retrieval (dense embeddings + BM25 + RRF fusion + MMR + HyDE) over a corpus of **real TMMIS deputation letters** scraped from Toronto's council record.
- **Council vote** (`vote-predictor`) — a Reasoner + deterministic Skeptic panel grounded in **196 real Toronto development-application outcomes** (147 approved / 49 refused); only claims supported by the record or cited precedent ship.

See `docs/DATA.md` for the verified sources.

## The on-device LLM stack

Everything runs locally on the GB10 — no external API is ever called, so the pipeline's unit economics are a one-time hardware cost:

- **Generation** — NVIDIA **`nemotron-3-super`** (120B-A12B hybrid Mamba-Transformer MoE) in **NVFP4**, served by **vLLM** on `:8001`. NVFP4 keeps the 120B model inside 128 GB, and vLLM's continuous batching runs the pipeline's concurrent LLM calls in parallel (which Ollama can't, for this architecture).
- **Embeddings** — `nomic-embed-text` via Ollama.
- **Reasoning toggle** — chain-of-thought is on for the analytical vote Reasoner and off for throwaway/generative steps (opposition HyDE & letters) to cut latency.

Setup, the exact vLLM command, and the connector env vars are in **`docs/LOCAL_LLM.md`**.

## The six components

Six independent sub-projects; the **connector** orchestrates them. The only stable interfaces are the five contracts in `docs/CONTRACTS.md`.

| # | Component | What it does | Status |
|---|---|---|---|
| 1 | `vote-predictor/` | Grounded multi-agent council-vote panel on local nemotron | Real corpus (196 precedents) |
| 2 | `opposition-generator/` | Hybrid-RAG opposition forecast over real TMMIS deputations | Real, on vLLM |
| 3 | `massing-generator/` | Deterministic interactive 3D massing from the envelope | Real, instant |
| 4 | `site-proforma/` | Real Toronto zoning + constraints + financial pro-forma | Real |
| 5 | `connector/` | LangGraph orchestrator; FastAPI + SSE streaming, warmup, caching | Real |
| 6 | `ui/` | Toronto map, streamed brief viewer, 3D, scenario controls, export | Real |

## Run it

The shared vLLM server runs on the GB10 (see `docs/LOCAL_LLM.md` to start it). Then:

```bash
# 1. Connector — points generation at the shared vLLM server, embeddings at Ollama
bash scripts/run_connector_vllm.sh          # → http://localhost:8000
#    (over Tailscale: VLLM_URL=http://<box>:8001/v1 bash scripts/run_connector_vllm.sh)

# 2. UI (separate terminal)
cd ui && npm install && npm run dev          # → http://localhost:3000

# 3. Any single component in isolation
uv run python -m vote_predictor.cli demo
uv run python -m opposition_generator.cli demo
uv run python -m massing_generator.cli demo
uv run python -m site_proforma.cli demo
```

`uv sync` at the repo root installs all backend components into one venv. Each component has its own `README.md` with setup notes.

## Docs

- `docs/PRD.md` — what we're building and why
- `docs/CONTRACTS.md` — the five interface contracts (source of truth)
- `docs/DATA.md` — verified Toronto Open Data + TMMIS sources
- `docs/LOCAL_LLM.md` — the on-device vLLM / nemotron setup + how to run against it
- `docs/COMPETITIVE_ANALYSIS.md` · `docs/VOTE_PREDICTOR.md` — feature/eval notes

## Stack

Python 3.12 (uv workspace) · FastAPI · LangGraph · Pydantic v2 · **vLLM** (NVFP4 nemotron-3-super) · Ollama (nomic-embed) · httpx · shapely · pyshp · rank-bm25 · Plotly (3D) · Playwright (TMMIS scrape) · Next.js 14 · TypeScript · react-leaflet · Tailwind

Built for the NVIDIA Spark Hack Series · ASUS GX10 / NVIDIA GB10 · Toronto, 2026.
