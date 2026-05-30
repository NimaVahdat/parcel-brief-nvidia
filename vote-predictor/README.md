# vote-predictor

## What this does

Predicts how Toronto council will vote on a development application — overall
approval probability, per-councillor lean, swing councillors, and counterfactual
**levers** ("+12 affordable units → +0.16"). It answers: *will this get approved,
and what change flips a no to a yes?*

## How it works — prediction by precedent (RAG, not a trained model)

Council approvals are decided by **precedent**: similar projects, in similar areas,
tend to get similar outcomes. So instead of training a classifier on features that
are buried in free-text staff reports, this component **retrieves the most similar
past applications (with their real council outcomes) and predicts from them.**

```
ApplicationFeatures → query → hybrid retrieve K similar past applications
  → approval_probability = similarity-weighted approval rate of the K neighbors
  → levers = counterfactual retrieval (perturb the application, re-retrieve, Δ prob)
  → per_councillor from precedents' recorded votes (sparse) + base-rate fallback
```

Why RAG over XGBoost here: the structured features a tabular model needs aren't
cleanly available (they live in prose), and a precedent approach is **explainable**
("0.73 — 6 of 8 similar Toronto applications were approved") and reuses the proven
opposition-generator retrieval stack. See `docs/PRD.md` for the original framing.

## Contract

```python
def predict(application: ApplicationFeatures, councillors: list[str]) -> VotePrediction
```

`predict()` never raises — it degrades `rag → heuristic` so the connector stays up.
Types in `src/vote_predictor/schemas.py`; source of truth in `docs/CONTRACTS.md`.

## The corpus — real Toronto outcomes

Past planning items (`PLAN_ACT`) scraped from the TMMIS council JSON API (reusing the
headful-browser Akamai bypass from opposition-generator), API-only so it is fast. The
council outcome (approved/refused) comes from the decision-report title + item status.
The embedded `text` strips outcome words so retrieval matches the project, not the label.

## Measuring quality

Because every precedent has a **known real outcome**, we can actually backtest:

```
python -m eval.evaluate     # leave-one-out over the corpus
```

Reports **accuracy, AUC, Brier (calibration), and lift over the base rate** — the
honest bar, since Toronto approves most applications.

**What the backtest tells us (honest results):**
- On the **feature-rich seed** corpus the method separates cleanly (AUC ~1.0) — the
  retrieval + probability machinery is sound.
- On the **real title-only corpus** (73 scraped precedents: 56 clean approvals, 17
  amended; base rate 0.77) it shows **AUC ~0.54, ~0 lift** — i.e. *no predictive
  signal*. This is a real finding, not a bug: **agenda titles don't contain the
  features that predict contention** (height, units, affordable share, opposition
  live in the staff-report PDF, not the title). Toronto also approves nearly
  everything that reaches a decision, so the predictable target is clean approval
  vs council-imposed amendment.

**The path to real predictive lift** is richer features: embed the staff-report
description (parse the `backgroundfile` PDF) or join the Development Applications
open dataset, instead of the agenda title alone. The retrieval/probability/lever
machinery stays the same.

`per_councillor` and `levers` have no counterfactual ground truth and are
face-validity checks only.

## Run it

```bash
pip install -e vote-predictor              # core (no xgboost/torch)
vote-predictor seed                        # synthetic precedent corpus
vote-predictor build-index                 # embed it (needs Ollama)
vote-predictor demo                        # full VotePrediction (+ which tier ran)

# real corpus (headful browser beats Akamai — use a real DISPLAY):
DISPLAY=:1 vote-predictor scrape --meeting-lo 27000 --meeting-hi 27210
vote-predictor build-index

# optional service
uvicorn vote_predictor.service:app --port 8001
```

## Configuration

| Env var | Meaning | Default |
|---|---|---|
| `OLLAMA_URL` | Ollama server | `http://localhost:11434` |
| `VP_EMBED_MODEL` | embedding model | `nomic-embed-text` |
| `DATABASE_URL` | set → pgvector instead of SQLite | unset |
| `VP_TOP_K` | precedents retrieved | `12` |

## File map

| File | Purpose |
|---|---|
| `infer.py` | `predict()` — THE CONTRACT + orchestration + degradation |
| `precedent.py` | probability, levers (counterfactual retrieval), per-councillor |
| `embed.py` · `store.py` · `retrieve.py` | the RAG stack (Ollama + SQLite/pgvector + hybrid) |
| `ingest.py` | TMMIS council-API scraper (planning items + outcomes) |
| `corpus.py` · `seeds.py` | corpus loading + committed synthetic precedents |
| `eval/evaluate.py` | leave-one-out backtest (accuracy/AUC/Brier/lift) |
| `cli.py` · `service.py` | CLI + optional FastAPI on :8001 |

## Honest limits

- `per_councillor` is data-limited (recorded votes are sparse, and the connector
  passes placeholder councillor IDs today) → best-effort estimate.
- Calibration is precedent-based, not a trained classifier — but explainable and
  measurable (see eval).

## Notes for the team

- `connector/agents/approvals.py` passes hardcoded `DEFAULT_COUNCILLORS` and
  `neighborhood="Trinity-Bellwoods"`; both should come from the parcel's ward/site
  lookup for real per-councillor output.
