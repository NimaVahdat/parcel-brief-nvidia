# parcel-brief

**An AI co-developer for Toronto real estate that runs entirely on a single NVIDIA GB10.**

Click a Toronto parcel on the map and get a decision-grade **Development Brief** in a few minutes: the legal building envelope, site constraints, an interactive 3D massing, a financial pro-forma, a predicted council vote, and a community-opposition forecast — every section grounded in real public data, not a generic model's guesses. It compresses a four-to-eight-week, **$150K–$300K** pre-acquisition consultant workflow into one **local-GPU** stack with **no cloud LLM and no per-token bill**.

> Built for the **NVIDIA Spark Hack Series** on an **ASUS GX10 / NVIDIA GB10** (128 GB unified memory). The whole reasoning stack — including a **120B-parameter** model — runs on-device.

## What it does, end to end

A click on a parcel fans out through a LangGraph pipeline and streams back a brief:

1. **Site & zoning** — legal envelope (height, FSI, setbacks, uses) + constraints (heritage, fire distance, transit, tree canopy) from Toronto Open Data.
2. **3D massing** — interactive retail-base → podium → setback-tower massing fit to the envelope, rendered instantly (deterministic, no LLM).
3. **Pro-forma** — construction cost, rent, sale, debt service, 5/10-yr IRR + sensitivities.
4. **Council vote** — a grounded multi-agent panel predicts approval probability from Toronto's real application-outcome record.
5. **Community opposition** — expected letter volume, ranked concerns, organized groups, and sample deputation letters in the neighbourhood's actual voice.
6. **Recommendation** — buy / conditional / pass with a 0–100 developability score.

You can also adjust the building (height / units / affordable / retail) and re-run — the pro-forma, vote, opposition, and recommendation all re-evaluate *your* building.

## Architecture

**Client ↔ server**

```
 Browser ──click parcel──►  Next.js UI (:3000) ──GET /analyze/stream──►  connector (:8000)
    ▲                                                                          │
    └───────────────  SSE: per-node progress + final BriefResponse  ◄──────────┘
```

**The connector is a LangGraph StateGraph.** Each node is owned by one component; the
arrows are the real edges (some branches run in parallel):

```
   LangGraph node            owned by                  data / backend it calls
 ─────────────────────────────────────────────────────────────────────────────────
   START
     ├─► zoning ──────┐
     │                ├─ run in ──   site-proforma  ──►  Toronto Open Data
     └─► constraints ─┘  parallel    site-proforma       (zoning, height, heritage,
                      │                                    fire, transit · GeoJSON+shapely)
                      ▼
                  massing            massing-generator ►  deterministic 3D massing (Plotly)
                      ▼
                  proforma           site-proforma     ►  financial model (IRR, sensitivities)
                      │
          ┌───────────┴───────────┐
          ▼          run in        ▼
      approvals      parallel    community
          │                        │
      vote-predictor           opposition-generator
      Reasoner + Skeptic,      hybrid RAG: dense+BM25+RRF
      196 real precedents      +MMR+HyDE over TMMIS letters
          │                        │
          └───────────┬───────────┘
                      ▼
                  principal          connector        ►  go/no-go + developability score
                      ▼                                   (deterministic synthesis)
                     END  ──►  BriefResponse
```

**LLM backends — all on the NVIDIA GB10 (128 GB, fully on-device, no cloud):**

```
   approvals · community · HyDE · letters  ──►  vLLM   nemotron-3-super NVFP4 (:8001)
                                                       continuous batching · reasoning toggle
   retrieval embeddings                    ──►  Ollama nomic-embed-text       (:11434)
```

Six independent components communicate only through the five contracts in `docs/CONTRACTS.md`; the connector is the only thing that imports the others.

| # | Component | What it does | Status |
|---|---|---|---|
| 1 | `vote-predictor/` | Grounded Reasoner + Skeptic council-vote panel | Real 196-precedent corpus *(see limitations)* |
| 2 | `opposition-generator/` | Hybrid-RAG opposition forecast over real TMMIS deputations | Real, on vLLM |
| 3 | `massing-generator/` | Deterministic interactive 3D massing from the envelope | Real, instant |
| 4 | `site-proforma/` | Real Toronto zoning + constraints + financial pro-forma | Real |
| 5 | `connector/` | LangGraph orchestrator; FastAPI + SSE, warmup, caching | Real |
| 6 | `ui/` | Map, streamed brief viewer, 3D, scenario controls, export | Real |

## Quick start

The shared **vLLM** server runs on the GB10 (start it per `docs/LOCAL_LLM.md`). Then:

```bash
uv sync                                  # installs all backend components into one venv

# 1. Connector — generation → vLLM, embeddings → Ollama
bash scripts/run_connector_vllm.sh       # → http://localhost:8000

# 2. UI (separate terminal)
cd ui && npm install && npm run dev       # → http://localhost:3000  (click a parcel)

# Any single component in isolation:
uv run python -m vote_predictor.cli demo
uv run python -m opposition_generator.cli demo
uv run python -m massing_generator.cli demo
uv run python -m site_proforma.cli demo
```

## Reproducing the demo (env / no API keys)

**No API keys are required — the entire stack is local.** Configuration is env vars only;
`scripts/run_connector_vllm.sh` sets them, or copy this sample `.env`:

```bash
# Generation → shared vLLM (nemotron-3-super NVFP4 on :8001).
# Over Tailscale, replace localhost with the box host.
VOTE_PREDICTOR_LLM_URL=http://localhost:8001/v1
VOTE_PREDICTOR_LLM_MODEL=nemotron-3-super
OPP_LLM_BASE_URL=http://localhost:8001/v1
OPP_LLM_MODEL=nemotron-3-super
# Embeddings → Ollama (nomic-embed-text)
OLLAMA_URL=http://localhost:11434
# Massing uses the instant deterministic renderer (no LLM)
MASSING_USE_MOCK=1
```

Starting the vLLM server (NVFP4 nemotron on the GB10) and the one-time box setup are in **`docs/LOCAL_LLM.md`**. The first request triggers a background warmup (loads GIS layers + makes the model resident) so subsequent briefs are fast; results are cached per parcel.

## Datasets & provenance

All real, all public — fetched/scraped into each component's gitignored `data/`:

- **Toronto Open Data** (CKAN / open.toronto.ca) — Zoning By-law areas + Height overlays, Property Boundaries, Heritage register, Fire-station locations, Transit stops, Neighbourhoods, Ward boundaries. Used by `site-proforma` and `connector` (shapely point-in-polygon over the GeoJSON).
- **TMMIS council record** (app.toronto.ca/tmmis) — real **community deputation letters**, scraped via Playwright (the site is behind Akamai), tagged and indexed into the opposition RAG corpus (`opposition-generator/data/deputations.jsonl`).
- **Toronto development-application outcomes** — **196 real applications** with real decisions (147 approved / 49 refused), with structured features parsed from the application text; this is the `vote-predictor` precedent corpus (`vote-predictor/data/precedents.jsonl`).
- **Models** — `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` (via the ungated `unsloth/...` mirror; NVIDIA Open Model License) and `nomic-embed-text`.

**Synthetic data:** during scaffolding the vote-predictor shipped a *synthetic* corpus (placeholder `SYN-*` applications + fabricated councillor votes) so the pipeline ran day-one. It has been **replaced by the real 196-precedent corpus** above. Toronto's per-councillor recorded votes are sparse (only contentious items get a recorded vote), so per-councillor profiles are not yet built from real data — see limitations.

## Known limitations & next steps

- **Vote prediction is grounded but not yet per-parcel.** The approval probability is now driven by the real 147/196 ≈ 0.75 base rate, but the model still abstains to that prior rather than varying per project. **Next:** a deterministic precedent-outcome prior (approval rate among the *k* most similar real precedents) so the number moves per parcel; and real per-councillor profiles once TMMIS recorded votes are ingested.
- **Throughput.** The GB10 is memory-bandwidth-bound, so NVFP4 nemotron runs at ~15 tok/s; a full fresh brief is ~70 s (warm). vLLM batches concurrent calls, so this improves as the pipeline parallelizes.
- **Single shared GPU.** nemotron (120B) is too large to run on both vLLM and Ollama at once, so vLLM owns the GPU and Ollama serves only embeddings.
- **Massing** is the deterministic renderer; an LLM spec-generation path exists but is off by default (slower, not needed for the brief).
- **Scope.** Toronto only; pro-forma cost/rent assumptions are heuristic baselines, not a live market feed.

## Docs

- `docs/PRD.md` — what we're building and why
- `docs/CONTRACTS.md` — the five interface contracts (source of truth)
- `docs/DATA.md` — verified Toronto Open Data + TMMIS sources
- `docs/LOCAL_LLM.md` — the on-device vLLM / nemotron setup + how to run against it
- `docs/COMPETITIVE_ANALYSIS.md` · `docs/VOTE_PREDICTOR.md` — feature/eval notes

## Stack

Python 3.12 (uv workspace) · FastAPI · LangGraph · Pydantic v2 · **vLLM** (NVFP4 nemotron-3-super) · Ollama (nomic-embed) · httpx · shapely · pyshp · rank-bm25 · Plotly (3D) · Playwright (TMMIS scrape) · Next.js 14 · TypeScript · react-leaflet · Tailwind

Built for the NVIDIA Spark Hack Series · ASUS GX10 / NVIDIA GB10 · Toronto, 2026.
