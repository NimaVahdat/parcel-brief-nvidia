# Vote Predictor — System Documentation

Semi-high-level reference for the `vote-predictor/` component: what it does, the agents
involved, the datasets it grounds on, and how information flows from raw Toronto records to a
verified, evidence-backed forecast. For the exact data sources see [DATA.md](DATA.md); for the
frozen interface see Contract 1 in [CONTRACTS.md](CONTRACTS.md); for the local-model deployment
see [LOCAL_LLM.md](LOCAL_LLM.md).

## Overview

Given a proposed development application and the councillors on the relevant committee, the
component predicts **how council will vote** — an overall approval probability, a per-councillor
Yes-probability where a councillor's record supports one, the swing councillors, and
counterfactual levers ("+12 affordable units → +0.16"). Every per-councillor probability ships
with the evidence behind it, and where there is no grounding the system **abstains to a flagged
prior rather than fabricating a number**.

It is a **grounded multi-agent panel** running entirely on local NVIDIA hardware (the GB10): a
reasoning model proposes, a deterministic auditor gates, and exact math aggregates. No external
API is called at inference.

```
ApplicationFeatures + committee councillors
        │
        ▼
  ┌─────────────┐   grounding    ┌──────────────────────────────────────────┐
  │  Retrieval  │───────────────▶│              The Panel                     │
  │ profiles +  │  records,      │  Reasoner (LLM)  →  Skeptic (rules)  →     │
  │ precedent   │  staff rec,    │  per-councillor      audit / abstain       │
  │ (embeddings)│  precedent     │  p_yes + evidence    only grounded ships    │
  └─────────────┘                │            │                               │
                                 │            ▼                               │
                                 │      Clerk (Poisson-binomial majority)     │
                                 └──────────────────────────────────────────┘
        │
        ▼
  VotePrediction (Contract 1)  +  agent_trace (additive: reasoning + verdicts)
```

## The agents

The panel is three specialists with deliberately different natures — a creative reasoner, a
skeptical rule-based auditor, and exact arithmetic. The split is what makes the output
defensible: the model proposes, but it cannot fabricate a probability that survives the audit.

| Agent | Nature | Responsibility |
|---|---|---|
| **Reasoner** | LLM (nemotron-3-super) | For each councillor, reason from *that* councillor's voting record, the staff recommendation, and retrieved precedent; emit a Yes-probability, a one-line rationale, and the **evidence ids** it used. Large rosters are chunked so each call stays within the model's budget. |
| **Skeptic** | Deterministic gate | Adversarially audit every Reasoner claim against the actual record. A claim with **no councillor history and no valid cited precedent is rejected** and forced to the councillor's prior (flagged `grounded=false`); a claim that strays far from the record without precedent support is pulled back. Only grounded claims ship. |
| **Clerk** | Exact math | Combine the surviving per-councillor probabilities into a committee approval probability via the **exact Poisson-binomial** distribution, and flag swing councillors. The LLM never does the committee arithmetic. |

The Skeptic being **rule-based, not another LLM**, is intentional: "only grounded claims ship"
is then a real, testable mechanism rather than a hope. When no model server is reachable (CI, or
a laptop without the GB10), the Reasoner degrades to a transparent record+staff heuristic and the
same Skeptic and trace still apply — so the contract never hard-fails.

## Datasets

Three Toronto sources, joined by a crosswalk because they share no common key. Full access
details and the Phase-0 grounding analysis are in [DATA.md](DATA.md).

| Source | Role | Access |
|---|---|---|
| **CKAN — Development Applications (AIC)** | The application corpus (address, ward, type, status, description). | Open CKAN datastore over plain HTTP. Deduped on `FOLDERRSN` (≈26k events → ≈8.5k applications). |
| **TMMIS — Member Voting Record** | The **labels**: recorded per-councillor Yes/No votes. | The City's downloadable CSV per term (or the Akamai-gated export via a headless browser). `Absent`/recused rows are dropped; each item's main disposition motion is the label. |
| **TMMIS — staff reports** | The single strongest feature: City Planning's recommendation. | Report PDFs in the plain-HTTP legdocs tree; a title-first classifier reads approve / approve-with-conditions / refuse. |

### The crosswalk (the linchpin)

CKAN applications and TMMIS votes have **no shared identifier**. Linking them is a three-hop
chain — deterministic at its ends, scrape-bound in its middle:

```
application_id (AIC APPLICATION#)
   └─[exact: the same number printed in the staff-report PDF]→ staff report + agenda item
                                                               └─[exact: item id]→ recorded votes
```

When the staff-report bridge is absent, the crosswalk falls back to a fuzzy **address +
committee + date-window** match, accepted only when unique. Every link carries a
`join_confidence` so the panel can down-weight or abstain on weak links. This is what lets the
real (non-synthetic) training table actually join — and, honestly, coverage is low (most
applications never reach a *recorded* committee vote), which is exactly why the system must
abstain on the majority rather than guess.

## Information flow

### Ingestion (offline, builds the local corpus)

```
CKAN AIC ──► dedup (FOLDERRSN) ──┐
TMMIS CSV ─► parse Yes/No, main motion ─► crosswalk ─► applications.parquet
staff PDFs ► title-first classify ──────┘  (app↔item↔vote   votes.parquet (+ application_id)
                                            + confidence)    crosswalk.parquet
                                                            ──► councillor profiles (train-only safe)
                                                            ──► nomic-embed-text application index
```

### Inference (per request — Contract 1 `predict`)

1. **Ground** — load the councillor's voting profile (smoothed yes-rate + lean), fetch the staff
   recommendation by id, and retrieve the *k* most similar past applications by semantic
   similarity over real application text (nomic-embed-text), with a feature-distance fallback.
2. **Reason** — the per-councillor Reasoner returns `p_yes`, a rationale, and cited evidence ids.
3. **Audit** — the Skeptic validates each claim against the record; ungrounded or over-confident
   claims are rejected/pulled back; survivors are marked grounded with their basis.
4. **Aggregate** — the Clerk computes the committee approval probability and swing councillors.
5. **Trace** — the per-councillor reasoning, Skeptic verdicts, and cited evidence are assembled
   into an additive `agent_trace`.

The function returns a Contract-1 `VotePrediction` (unchanged shape); `predict_with_trace` and
the service additionally return `agent_trace` for a UI drill-down — Contract 1 and the required
service fields are untouched.

## Grounding & verification

Verification is built into the data path, not bolted on:

- **The Skeptic gate** is the structural guarantee that an ungrounded probability cannot ship —
  it abstains to a clearly-flagged prior instead of inventing a confident number.
- **The evidence trace** makes every probability auditable: which councillor record (n votes,
  yes-rate), which precedent application ids, and which staff recommendation it rests on, plus
  the Skeptic's accept/reject/abstain decision per councillor.
- **The evaluation harness** backtests the panel on a **leakage-safe temporal split** (councillor
  profiles and retrieved precedent are restricted to the training period, so test outcomes never
  leak into grounding) against (i) the deterministic fallback and (ii) a **no-grounding LLM
  ablation** routed through the same Skeptic — and reports per-councillor accuracy / AUC / Brier,
  contested-item outcome accuracy, and the panel's **abstain rate** so a silently-degrading panel
  is visible rather than mistaken for the baseline.

## Local models & boundaries

- **Reasoning:** nemotron-3-super served by Ollama on the GB10 (OpenAI-compatible). A vLLM FP8
  endpoint is a supported stricter-JSON fallback. The wrapper is reasoning-model-safe: it reads
  the answer from `content`, falls back to the separate `reasoning` field, and strips `<think>`.
- **Embeddings:** nomic-embed-text (768-dim) on the same box, with a deterministic feature-
  distance fallback when the endpoint is unreachable.
- **Boundaries:** Contract 1's `predict(application, councillors) → VotePrediction` is frozen; the
  evidence trace is purely additive. The component never imports another component; only the
  connector imports it. All inference is local — no external API.
