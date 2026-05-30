# site-proforma

## What this does

Two related responsibilities, exposed as two functions:

1. **Site lookup** — given a Toronto parcel ID, return the legal building envelope (from the zoning bylaw spatial layer) and the site constraints (heritage, tree canopy, sun-shadow, transit, conservation, easements).
2. **Pro-forma** — given a candidate massing and the site data, return construction cost, projected rents (from CMHC), debt service, IRR over 5 and 10 years, and sensitivities.

## Contract

```python
def lookup(parcel_id: str) -> SiteData
def calculate(massing: Massing, site: SiteData) -> FinancialModel
```

Full type definitions in `src/site_proforma/schemas.py`. Source of truth in `docs/CONTRACTS.md`.

## Data sources

- **Zoning By-law 569-2013** (spatial layer)
- **Property Boundaries** (parcels)
- **Heritage Register**, **Street Tree Data**, **TTC GTFS**, **TRCA regulated areas**
- **Tall Building Design Guidelines** (sun-shadow rules) — parsed from the PDF
- **CMHC Rental Market Survey** — neighborhood-level rents
- **StatsCan 2021 Census** — neighborhood demographics

All URLs in `docs/DATA.md`. Local dumps to `./data/` (gitignored). Source-of-truth tables persist to Postgres+PostGIS (shared docker-compose).

## How to run solo

```bash
# from repo root
docker compose up -d           # need Postgres for spatial queries
uv sync

# look up a mock parcel
uv run python -m site_proforma.cli lookup --parcel-id 543-dundas-w

# run a mock pro-forma
uv run python -m site_proforma.cli proforma --demo

# OR standalone service on :8004
uv run uvicorn site_proforma.service:app --port 8004 --reload
```

## Current state

- [x] Skeleton scaffolded, both contract functions return mock data
- [x] CLI runs end-to-end
- [x] Standalone FastAPI service runs
- [ ] Toronto Open Data ingestion → Postgres+PostGIS (`ingest_open_data.py`)
- [ ] CMHC rental tables ingestion (`ingest_cmhc.py`)
- [ ] StatsCan census ingestion (`ingest_statscan.py`)
- [ ] Real `lookup()` against PostGIS (spatial join parcel ↔ zoning, heritage, etc.)
- [ ] Real `calculate()` with Toronto cost benchmarks + CMHC rents + DCF math

## Next tasks

1. `ingest_open_data.py`: download zoning, parcels, heritage, trees, TTC GTFS, TRCA. Load to PostGIS with `geopandas.GeoDataFrame.to_postgis`. Each table indexed on `geom`.
2. Implement `site.lookup`: spatial join parcel to applicable zoning polygon; LEFT JOIN to heritage, trees within 30m, TRCA, transit < 500m. Return a populated `SiteData`.
3. `ingest_cmhc.py`: parse the CMHC rental survey XLSX. Store by neighborhood + bed count.
4. `proforma.calculate`: implement the financial math. Standard Toronto cost-per-sqft for the massing's GFA. Annual rent = sum(units × CMHC neighborhood rent × 12). Debt service at assumed rate. IRR over 5 and 10 years with terminal cap.

## File map

| File | Purpose |
|---|---|
| `src/site_proforma/__init__.py` | Re-exports `lookup()` and `calculate()` |
| `src/site_proforma/schemas.py` | Pydantic types |
| `src/site_proforma/ingest_open_data.py` | Toronto Open Data ETL → PostGIS |
| `src/site_proforma/ingest_cmhc.py` | CMHC XLSX → Postgres |
| `src/site_proforma/ingest_statscan.py` | StatsCan census → Postgres |
| `src/site_proforma/site.py` | `lookup()` — CONTRACT |
| `src/site_proforma/proforma.py` | `calculate()` — CONTRACT |
| `src/site_proforma/service.py` | Optional FastAPI on :8004 |
| `src/site_proforma/cli.py` | Solo demo CLI |
| `tests/test_smoke.py` | Smoke test |
