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

- **Transit distance is real** — computed (haversine) from actual TTC subway-station
  coordinates.
- **Zoning envelope is a deterministic, location-aware gradient** (downtown → high
  density, avenues → mid-rise, neighbourhoods → low-rise) derived from distance to
  the core — a defensible screening estimate.
- Heritage / sun-shadow / conservation use sensible rules (e.g. a shadow-study rule
  triggers for ≥30 m buildings).

The fully-legal envelope needs the City's **Zoning By-law spatial layer**
(point-in-polygon). That's the documented next step — drop the GeoJSON at
`data/zoning.geojson` and wire `_zoning_from_geojson` (install the `gis` extra). The
contract and the pro-forma don't change.

## Run it

```bash
pip install -e site-proforma            # pure-Python, no GIS/DB needed
site-proforma lookup --parcel-id 43.6532_-79.3832
site-proforma proforma --parcel-id 43.6532_-79.3832
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
| `site.py` | `lookup()` — envelope + constraints (real transit, location-aware zoning) |
| `proforma.py` | `calculate()` — the real DCF + IRR + sensitivities |
| `assumptions.py` | env-overridable Toronto benchmarks |
| `schemas.py` · `cli.py` · `service.py` | contract types, CLI, FastAPI on :8004 |

## Honest scope

- `calculate()` is a **real, defensible DCF** (the high-value part).
- `lookup()` zoning is a **location-aware estimate**, not the legal spatial layer yet
  (transit distance is real). The GIS hook is documented above.

## Notes for the team

- The connector hardcodes `neighborhood` and councillors; once `lookup()` returns
  ward/neighbourhood metadata, opposition + vote components can stop hardcoding.
