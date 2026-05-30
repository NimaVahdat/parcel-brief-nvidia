# vote-predictor

## What this does

Predicts how Toronto council will vote on a development application: overall approval probability, per-councillor vote where individual votes are recorded, and counterfactual levers (e.g. "+12 affordable units → +0.16 probability").

The core is a tabular classifier (XGBoost) trained on past Toronto applications joined to recorded vote outcomes. A Qwen2.5-7B wrapper parses unstructured application text into structured features on the way in, and writes natural-language counterfactual recommendations on the way out.

## Contract

```python
def predict(application: ApplicationFeatures, councillors: list[str]) -> VotePrediction
```

Full type definitions in `src/vote_predictor/schemas.py`. Source of truth in `docs/CONTRACTS.md`.

## Data sources

- **TMMIS** — applications and recorded per-councillor votes (1999–present). See `docs/DATA.md` for URLs.
- TMMIS is Akamai-protected; scraping needs a headless browser (Playwright).

Local data is dumped to `./data/` (gitignored).

## How to run solo

```bash
# from repo root
uv sync

# print a mock prediction for a fake application
uv run python -m vote_predictor.cli demo

# OR run the standalone HTTP service on :8001
uv run uvicorn vote_predictor.service:app --port 8001 --reload
curl -X POST http://localhost:8001/predict -H "Content-Type: application/json" -d @example_input.json
```

## Current state

- [x] Skeleton scaffolded, contract function returns mock data
- [x] CLI runs end-to-end with a hardcoded fake application
- [x] Standalone FastAPI service runs
- [ ] TMMIS scraper for applications + recorded votes (`ingest.py`)
- [ ] Feature engineering on raw application data (`features.py`)
- [ ] XGBoost training pipeline + held-out evaluation (`train.py`)
- [ ] LLM wrapper: parse unstructured app text in, generate counterfactuals out (`llm_wrapper.py`)
- [ ] Replace mock in `infer.py` with model load + real prediction

## Next tasks

1. Implement the TMMIS scraper in `ingest.py` (Playwright; see the Akamai note in `docs/DATA.md`). Dump to `data/applications.parquet` and `data/votes.parquet`.
2. Define the feature set in `features.py`. Start with: project_height_m, total_units, affordable_units, retail_sqft, neighborhood (one-hot), committee_id, councillor histories.
3. Train an XGBoost classifier in `train.py`. Hold out the most recent 500 applications as test. Report accuracy + calibration.
4. Wire `infer.py` to load the trained model and return real predictions.
5. Add the LLM wrapper for the I/O layer.

## File map

| File | Purpose |
|---|---|
| `src/vote_predictor/__init__.py` | Re-exports `predict()` |
| `src/vote_predictor/schemas.py` | Pydantic types for this component (re-declared from contracts) |
| `src/vote_predictor/ingest.py` | TMMIS scraping |
| `src/vote_predictor/features.py` | Feature engineering |
| `src/vote_predictor/train.py` | XGBoost training |
| `src/vote_predictor/infer.py` | `predict()` — THE CONTRACT |
| `src/vote_predictor/llm_wrapper.py` | Qwen2.5-7B wrapper for I/O |
| `src/vote_predictor/service.py` | Optional FastAPI service on :8001 |
| `src/vote_predictor/cli.py` | Solo demo CLI |
| `tests/test_smoke.py` | Smoke test (mock prediction renders) |
