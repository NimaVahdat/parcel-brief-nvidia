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

Built from Toronto's **Development Applications open dataset** (CKAN, no Akamai, plain
HTTP, ~26k records). We keep the records with a **decided outcome** — approved
(`Council Approved`, `OMB Approved`, …) vs refused (`Refused`, `OMB Refused`) — for
major development applications, and **balance the classes** so the backtest is
non-trivial. Crucially, we embed each application's **DESCRIPTION** (storeys, units,
use) — the project features that actually predict outcomes — not just an address. The
DESCRIPTION is the applicant's proposal and contains no outcome, so there is no leakage.

(Toronto's TMMIS council API was the earlier source, but agenda *titles* lack project
features and gave no predictive signal — the open-data descriptions are the unlock.)

## Measuring quality

Every precedent has a **known real outcome**, so we backtest for real:

```
python -m eval.evaluate     # leave-one-out over the corpus
```

**Honest results on real Toronto data** (196 precedents, base rate 0.75 approved):

| metric | value | meaning |
|---|---|---|
| **AUC** | **0.84** | ranks refused below approved — genuinely discriminative (0.5 = random) |
| **balanced accuracy** | **0.85** | the right metric under class imbalance |
| Brier | 0.24 | calibration (lower is better) |
| accuracy @0.5 / raw lift | 0.54 / ~0 | **misleading** — at a 75% base rate, raw accuracy can't move; use AUC |

The approved sample is spread across the full date range so the model separates on
planning merit, not era. `per_councillor` and `levers` have no counterfactual ground
truth and are face-validity checks only (the levers do shift sensibly — a
modest+affordable project scores ~0.83 vs ~0.66 for an over-height, variance-heavy one).

## Run it

```bash
pip install -e vote-predictor              # core (no xgboost/torch)
vote-predictor seed                        # synthetic precedent corpus
vote-predictor build-index                 # embed it (needs Ollama)
vote-predictor demo                        # full VotePrediction (+ which tier ran)

# real corpus from Toronto's Development Applications open data (no browser needed):
vote-predictor fetch
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
