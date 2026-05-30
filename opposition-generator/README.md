# opposition-generator

## What this does

Predicts how hard a Toronto neighbourhood will fight a proposed development —
**before** the developer buys the land. For a given project in a given
neighbourhood it returns:

- **`expected_letter_count`** — how many objection deputations to expect
- **`top_concerns`** — what they'll object to, ranked (shadow, traffic, height, …)
- **`organized_groups`** — which residents' associations / BIAs will likely mobilize
- **`sample_letters`** — what the opposition will actually sound like
- **`mitigations`** — project changes historically associated with less opposition

It replaces a slice of the 4–8 week, $150K–$300K consultant brief with a few
seconds of local-GPU inference.

## Why it works

The City of Toronto publishes **every community deputation ever submitted** to
committee (on TMMIS, as PDFs). That is the moat. This component is
retrieval-augmented over that real record: it finds the past objections most
similar to the current situation and reads the real patterns out of them. The four
structured fields are **aggregated from real letters** — not invented. Only the
generated `sample_letters` involve an LLM, and they're grounded in the retrieved
real letters and constrained to concerns the neighbourhood actually raised.

## The contract

```python
def generate(project: ProjectDescription, neighborhood: str) -> OppositionForecast
```

This is the only stable interface (see `docs/CONTRACTS.md`). The connector imports
it as `from opposition_generator import generate`. `generate()` **never raises** —
it degrades gracefully (see below) so the orchestrator stays alive. Types are in
`src/opposition_generator/schemas.py`.

## How it works (pipeline)

```
TMMIS PDFs ─ingest─> deputations.jsonl ─embed─> vector store ─retrieve─> forecast ─> OppositionForecast
 (Playwright)        (LLM-tagged)       (Ollama)  (SQLite/pgvec) (HyDE+RRF+MMR)  (aggregate + generate)
```

1. **Ingest** (`ingest/`) — Playwright scrapes deputation PDFs from TMMIS;
   `extract.py` pulls text (`pypdf`, with a `pytesseract` OCR fallback for scans);
   `tag.py` runs a one-time **LLM pass** to label each letter with neighbourhood,
   canonical concerns, organizing groups, and project type → `data/deputations.jsonl`.
2. **Embed** (`index/embed.py`) — each letter is embedded via Ollama
   (`nomic-embed-text`, 768-d).
3. **Store** (`index/store.py`) — vectors + metadata go into a pluggable store:
   SQLite by default, Postgres + pgvector when `DATABASE_URL` is set.
4. **Retrieve** (`index/retrieve.py`) — **hybrid search**:
   - **HyDE**: the LLM drafts a hypothetical deputation for this project so we match
     letter-to-letter instead of spec-to-letter;
   - **dense** (embeddings) + **BM25** (lexical, catches addresses / group names) are
     fused with **RRF**, then **MMR** diversifies the winners.
   - Filters to the project's neighbourhood, broadening city-wide if it's thin.
5. **Forecast** (`forecast/`) — `aggregate.py` builds the grounded fields from the
   retrieved letters; `letters.py` produces the hybrid `sample_letters` (1–2
   LLM-generated, grounded + 1 real letter as evidence); `taxonomy.py` holds the
   fixed concern vocabulary and concern→mitigation map.

## Directory map

```
src/opposition_generator/
  __init__.py        # re-exports generate, schemas (contract surface)
  schemas.py         # Pydantic contract types
  config.py          # env-driven config
  llm.py             # Ollama chat client (JSON + retry)
  generate.py        # THE CONTRACT — orchestration + degradation tiers
  cli.py             # seed / build-index / retrieve / demo / scrape / ingest
  service.py         # optional FastAPI on :8002
  ingest/            # scrape.py · extract.py · tag.py
  index/             # embed.py · store.py · retrieve.py · corpus.py
  forecast/          # aggregate.py · letters.py · taxonomy.py
  seeds/             # committed synthetic corpus
tests/               # offline unit tests (RRF, MMR, taxonomy, store, smoke)
eval/                # leave-one-out retrieval eval harness
```

## Models & infra

| Piece | Default | Override |
|---|---|---|
| Embeddings | Ollama `nomic-embed-text` (768-d) | `OPP_EMBED_MODEL` |
| LLM | Ollama `nemotron-3-super:latest` | `OPP_LLM_MODEL` |
| Vector store | SQLite (`data/deputations.sqlite3`) | set `DATABASE_URL` → pgvector |

Ollama is the shared inference server on the GB10 (`:11434`). No torch, no Docker
required for the default path.

## Run it

```bash
pip install -e opposition-generator       # core (torch-free)
# optional: pip install -e 'opposition-generator[pg,scrape,ocr]'

opposition-generator seed                 # write synthetic corpus to data/
opposition-generator build-index          # embed it (needs Ollama)
opposition-generator retrieve -n Trinity-Bellwoods   # sanity-check hybrid hits
opposition-generator demo                 # full OppositionForecast (+ which tier ran)

# optional standalone service
uvicorn opposition_generator.service:app --port 8002
```

Building the real corpus (deliberate, outward-facing — see `docs/DATA.md`):

```bash
opposition-generator scrape --start-year 2022 --max-files 200   # needs [scrape]
opposition-generator ingest                                      # extract + LLM-tag
opposition-generator build-index
```

## Configuration

| Env var | Meaning | Default |
|---|---|---|
| `OLLAMA_URL` | Ollama server | `http://localhost:11434` |
| `OPP_EMBED_MODEL` | embedding model | `nomic-embed-text` |
| `OPP_LLM_MODEL` | generation model | `nemotron-3-super:latest` |
| `DATABASE_URL` | set → use pgvector | unset (SQLite) |
| `OPP_SQLITE_PATH` | SQLite file | `data/deputations.sqlite3` |
| `OPP_TOP_K` | retrieval depth | `8` |
| `OPP_DATA_DIR` | data directory | `./data` |

For shared-box isolation, give each dev their own `DATABASE_URL`/`OPP_SQLITE_PATH`
and service port.

## Degradation tiers

`generate()` always returns a valid `OppositionForecast`:

| Tier | When | Behaviour |
|---|---|---|
| `rag` | normal | hybrid retrieval + LLM-generated grounded letters |
| `retrieval` | LLM down | real retrieved data, templated letters |
| `heuristic` | store/embeddings down | sensible forecast from project params alone |

`generate_with_meta()` exposes which tier ran (used by the CLI/service for debug).

## Current state

- [x] Pipeline: ingest → embed → store → hybrid retrieve → forecast
- [x] Ollama embeddings + generation; SQLite/pgvector pluggable store
- [x] Hybrid retrieval (dense + BM25 + RRF + MMR + HyDE)
- [x] Hybrid sample letters (generated + real evidence) with concern guardrail
- [x] LLM-tagged ingest (Playwright scraper + pypdf/OCR) — coded
- [x] Graceful degradation tiers; offline tests; eval harness
- [ ] Run the full historical TMMIS scrape to build the real corpus
- [ ] Calibrated `expected_letter_count` regression on real volume data

## Notes for the team

- The connector currently hardcodes `neighborhood="Trinity-Bellwoods"` in
  `connector/agents/community.py`; it should come from the parcel's site data
  (`SiteData` has no `neighborhood` field yet — vote-predictor needs it too).
- `connector/agents/principal.py` ignores `community_response` in the go/no-go; our
  forecast (and `mitigations`) should feed the final recommendation.
