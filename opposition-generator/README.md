# opposition-generator

## What this does

Predicts the community opposition a Toronto development project will face. Generates plausible deputation letters in the voice of the actual neighborhood, surfaces the top concerns ranked by frequency, names the organized resident groups likely to mobilize, and suggests project changes historically associated with reduced opposition.

The pipeline is retrieval-augmented: sentence-transformer embeddings of the real Toronto deputation corpus are indexed in pgvector. At inference, the top-k most similar past deputations are retrieved for the (neighborhood, project type) pair, and a strong instruction-tuned open model adapts them to the current project. **No fine-tuning** — the retrieved letters carry the neighborhood voice.

## Contract

```python
def generate(project: ProjectDescription, neighborhood: str) -> OppositionForecast
```

Full type definitions in `src/opposition_generator/schemas.py`. Source of truth in `docs/CONTRACTS.md`.

## Data sources

- **TMMIS** — community deputations attached to committee agenda items as PDFs. See `docs/DATA.md`.
- Sample verified path: `legdocs/mmis/YYYY/<committee>/comm/communicationfile-<id>.pdf`.
- Expect ~10–20% of deputations to be image-only and need OCR fallback.

Local corpus is dumped to `./data/deputations/` (gitignored).

## How to run solo

```bash
# from repo root
uv sync

# mock generation for a fake project
uv run python -m opposition_generator.cli demo

# OR standalone service on :8002
uv run uvicorn opposition_generator.service:app --port 8002 --reload
```

## Current state

- [x] Skeleton scaffolded, contract function returns mock letters
- [x] CLI runs end-to-end
- [x] Standalone FastAPI service runs
- [ ] TMMIS deputation scraper (`ingest.py`)
- [ ] PDF text extraction + OCR fallback (`ingest.py`)
- [ ] Embedding pipeline using sentence-transformers (`embed.py`)
- [ ] pgvector index build (`embed.py`)
- [ ] Top-k retrieval with neighborhood + project-type filters (`retrieve.py`)
- [ ] LLM adaptation of retrieved letters to current project (`generate.py`)

## Next tasks

1. Scrape deputation PDFs from TMMIS (Playwright). Save raw PDFs to `data/deputations/raw/`.
2. Extract text with `pypdf`. Fall back to `pytesseract` OCR if the page contains no extractable text.
3. Embed each deputation with `sentence-transformers/all-mpnet-base-v2`. Store in Postgres + pgvector.
4. Build `retrieve.py`: given `(neighborhood, project_description)`, return top-k similar past deputations.
5. Build `generate.py`: prompt the local LLM with retrieved letters as in-context examples; ask it to write a letter in the same voice about the current project.

## File map

| File | Purpose |
|---|---|
| `src/opposition_generator/__init__.py` | Re-exports `generate()` |
| `src/opposition_generator/schemas.py` | Pydantic types |
| `src/opposition_generator/ingest.py` | TMMIS deputation scraping + PDF text extraction |
| `src/opposition_generator/embed.py` | Embed corpus into pgvector |
| `src/opposition_generator/retrieve.py` | Top-k similarity search |
| `src/opposition_generator/generate.py` | `generate()` — THE CONTRACT |
| `src/opposition_generator/service.py` | Optional FastAPI on :8002 |
| `src/opposition_generator/cli.py` | Solo demo CLI |
| `tests/test_smoke.py` | Smoke test |
