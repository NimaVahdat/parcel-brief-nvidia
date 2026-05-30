# site-proforma

## What this does

Two deterministic functions (no ML — GIS + finance):

1. **`lookup(parcel_id)`** — what can I legally build here, and what's in the way?
   The legal building envelope (height, FSI, setbacks, uses, parking) + site
   constraints (heritage, transit distance, sun/shadow, conservation, easements).
2. **`calculate(massing, site)`** — do the numbers work? Construction cost,
   projected rents, debt service, **IRR over 5 and 10 years**, and sensitivities.

## Contract

```python
def lookup(parcel_id: str) -> SiteData
def calculate(massing: Massing, site: SiteData) -> FinancialModel
```

`parcel_id` is the map-click point the UI sends as `"lat_lng"` (see `ui/ParcelMap`).
Types in `src/site_proforma/schemas.py`; source of truth in `docs/CONTRACTS.md`.

## The pro-forma (`calculate`) — a real DCF

A transparent, deterministic discounted-cash-flow model:

```
construction cost = GFA × cost/m² (hard + soft + contingency)
stabilized NOI    = (gross rent × (1−vacancy) + retail) × (1 − opex)
stabilized value  = NOI / cap rate
IRR (5y, 10y)     = equity out → (NOI − debt service)/yr → sale at horizon
sensitivities     = rate ±100bp, rent ±10%, +6mo stabilization
```

Every assumption (cost benchmarks, CMHC-level rents, LTC, interest, cap rate,
timing) lives in `assumptions.py` and is **env-overridable** — order-of-magnitude
Toronto benchmarks, decision-grade for screening. Affordable units rent at a
configurable discount, so the pro-forma reflects the affordability trade-off the
other components surface.

## The site lookup (`lookup`)

- **Zoning envelope is real** — point-in-polygon over the City's **Zoning By-law
  569-2013** open data: max height from the Height Overlay, FSI from the Zoning Area
  layer (`FSI_TOTAL`), permitted uses from the zone category (`ZN_ZONE`). Where the
  by-law leaves an attribute unspecified in the geometry, a sensible zone-category
  default fills in. Run `site-proforma fetch-zoning` once to download the layers
  (~14k polygons); without them, `lookup()` degrades to a location-aware estimate.
- **Transit distance is real** — haversine from actual TTC subway-station coordinates.
- Sun-shadow / heritage / conservation use sensible rules (e.g. a shadow-study rule
  triggers for ≥30 m buildings). Heritage spatial join is the remaining next step.

Real examples: King/Bay → 84 m / FSI 12.0; Yonge-St Clair → 30 m / FSI 4.25; a North
York residential parcel → 10 m / FSI 0.6.

## Run it

```bash
pip install -e 'site-proforma[gis]'     # gis extra = shapely + httpx for real zoning
site-proforma fetch-zoning              # download the City zoning layers (once)
site-proforma lookup --parcel-id 43.6486_-79.3806
site-proforma proforma --parcel-id 43.6486_-79.3806
uvicorn site_proforma.service:app --port 8004     # optional service
```

## Configuration (selected)

| Env var | Meaning | Default |
|---|---|---|
| `SP_HARD_RES_PSM` | residential hard cost $/m² | 4300 |
| `SP_CAP_RATE` | terminal cap rate | 0.045 |
| `SP_LTC` | loan-to-cost | 0.60 |
| `SP_INTEREST_RATE` | debt rate | 0.062 |
| `SP_RENT_1BR` … | monthly rent by unit type | CMHC-level |

(Full list in `assumptions.py`.)

## File map

| File | Purpose |
|---|---|
| `site.py` | `lookup()` — envelope + constraints (real transit; real or fallback zoning) |
| `gis.py` | real zoning point-in-polygon over the City Zoning By-law layers |
| `proforma.py` | `calculate()` — the real DCF + IRR + sensitivities |
| `assumptions.py` | env-overridable Toronto benchmarks |
| `schemas.py` · `cli.py` · `service.py` | contract types, CLI, FastAPI on :8004 |

## Honest scope

- `lookup()` zoning (height / FSI / uses) is **real** — from the City Zoning By-law
  layers — with a graceful estimate fallback when the data isn't downloaded. Transit
  distance is real.
- `calculate()` is a **real, defensible DCF**; its cost/rent/cap-rate inputs are
  tunable Toronto benchmarks (not a live per-parcel feed).
- Still estimated: parcel footprint geometry (a ~20 m placeholder; the real parcel
  layer is separate) and heritage status (spatial join pending).

## Notes for the team

- The connector hardcodes `neighborhood` and councillors; once `lookup()` returns
  ward/neighbourhood metadata, opposition + vote components can stop hardcoding.
