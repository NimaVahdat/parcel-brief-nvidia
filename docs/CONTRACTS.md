# Interface Contracts

These five interfaces are the only stable contracts between components. Everything else inside a component is the owner's call. Any change to a contract requires team agreement and a synchronized update across the components that depend on it.

Each component re-declares these types as its own Pydantic models — components do not import each other.

## Shared Pydantic Types

```python
from pydantic import BaseModel
from typing import Literal

# ---- inputs / outputs used across contracts ----

class ZoningEnvelope(BaseModel):
    parcel_id: str
    max_height_m: float
    max_fsi: float
    setbacks: dict[str, float]          # {"north": 3.0, "south": 0.0, "east": 1.5, "west": 1.5}
    permitted_uses: list[str]           # ["residential", "retail", ...]
    footprint_polygon: list[tuple[float, float]]   # WGS84 (lon, lat) ring
    parking_minimum: int | None

class SiteConstraints(BaseModel):
    parcel_id: str
    heritage_status: Literal["none", "listed", "designated"]
    tree_canopy_area_m2: float
    sun_shadow_rules: list[str]
    conservation_overlays: list[str]
    transit_distance_m: float
    easements: list[str]

class SiteData(BaseModel):
    zoning_envelope: ZoningEnvelope
    constraints: SiteConstraints

class Massing(BaseModel):
    massing_id: str
    height_m: float
    total_gfa_m2: float
    unit_mix: dict[str, int]            # {"studio": 12, "1br": 30, "2br": 20, ...}
    retail_sqft: float
    affordable_units: int
    three_d_uri: str                    # path or URL to a .glb / .obj / .ply
    facade_renders: list[str]           # image URIs

class MassingOutput(BaseModel):
    options: list[Massing]

class FinancialModel(BaseModel):
    construction_cost: float
    projected_annual_rent: float
    projected_sale_price: float | None
    debt_service: float
    irr_5y: float
    irr_10y: float
    sensitivities: dict[str, dict[str, float]]    # {"rate_+100bp": {"irr_5y": ...}, ...}

class ApplicationFeatures(BaseModel):
    parcel_id: str
    height_m: float
    total_units: int
    affordable_units: int
    retail_sqft: float
    use_mix: dict[str, float]
    neighborhood: str
    requested_variances: list[str]

class Lever(BaseModel):
    change: str                         # "add 12 affordable units"
    delta_probability: float            # +0.16

class VotePrediction(BaseModel):
    approval_probability: float
    per_councillor: dict[str, float]    # {"councillor_id": probability_yes}
    swing_councillors: list[str]
    levers: list[Lever]

class ProjectDescription(BaseModel):
    height_m: float
    total_units: int
    affordable_units: int
    use_mix: dict[str, float]
    character_notes: str | None

class Letter(BaseModel):
    text: str
    inferred_concerns: list[str]
    source_neighborhood: str

class OppositionForecast(BaseModel):
    expected_letter_count: int
    sample_letters: list[Letter]
    top_concerns: dict[str, float]      # {"shadow": 0.78, "traffic": 0.40}
    organized_groups: list[str]
    mitigations: list[str]              # changes historically associated with reduced opposition

class GoNoGo(BaseModel):
    recommendation: Literal["buy", "pass", "conditional"]
    confidence: float
    dominant_sensitivities: list[str]
    rationale: str

class BriefResponse(BaseModel):
    parcel_id: str
    site_fundamentals: ZoningEnvelope
    site_constraints: SiteConstraints
    design_options: MassingOutput
    financial_model: FinancialModel
    approval_forecast: VotePrediction
    community_response: OppositionForecast
    recommendation: GoNoGo
```

## Contract 1 — `vote_predictor.predict`

```python
def predict(application: ApplicationFeatures, councillors: list[str]) -> VotePrediction:
    """
    Predict how Toronto council will vote on a development application.

    application: structured features of the proposed project.
    councillors: list of councillor IDs serving on the relevant committee.

    Returns probability of approval, per-councillor probability where individual
    votes are recorded, identified swing councillors, and counterfactual levers
    that would shift the outcome.
    """
```

## Contract 2 — `opposition_generator.generate`

```python
def generate(project: ProjectDescription, neighborhood: str) -> OppositionForecast:
    """
    Predict the community opposition to a project in a specific Toronto neighborhood.

    project: structured description of what is being proposed.
    neighborhood: e.g. "Trinity-Bellwoods", "Rosedale".

    Returns the expected volume and content of deputations, sample letters in
    the voice of the actual neighborhood, named local groups likely to mobilize,
    and project changes historically associated with reduced opposition.
    """
```

## Contract 3 — `massing_generator.generate`

```python
def generate(envelope: ZoningEnvelope) -> MassingOutput:
    """
    Generate viable 3D building massings that fit a zoning envelope.

    envelope: the legal building envelope from the site lookup.

    Returns two or three Massing options, each with a 3D model URI and facade
    renders. Style respects Toronto vernacular where the optional LoRA is loaded.
    """
```

## Contract 4 — `site_proforma`

This component exports two functions because site lookup and pro-forma math are independent operations.

```python
def lookup(parcel_id: str) -> SiteData:
    """
    Look up zoning envelope and site constraints for a Toronto parcel.

    Sources: Toronto Open Data (zoning bylaw spatial layer, parcels, heritage
    register, tree canopy, transit, sun-shadow rules, conservation overlays).
    """

def calculate(massing: Massing, site: SiteData) -> FinancialModel:
    """
    Compute construction cost, projected rents/sales, debt service, IRR over
    5 and 10 years, and sensitivities.

    Uses CMHC neighborhood rents and standard Toronto construction cost benchmarks.
    """
```

## Contract 5 — `connector` HTTP API

```
POST /analyze
Content-Type: application/json
Body:    { "parcel_id": str }
Returns: BriefResponse (as defined above)
```

The UI consumes this response directly and renders it.

## Change Process

If you need to evolve a contract:

1. Propose the change in team chat with the new shape.
2. Update `docs/CONTRACTS.md` and the components that produce or consume the changed field, in a single commit.
3. Run the verification flow in `README.md` end-to-end before pushing.
