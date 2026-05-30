"""BriefResponse — the final contract between connector and UI. See docs/CONTRACTS.md."""

from typing import Literal

from pydantic import BaseModel


# Re-declare component types so the connector doesn't import component internals.
# These shapes must match docs/CONTRACTS.md exactly.


class ZoningEnvelope(BaseModel):
    parcel_id: str
    max_height_m: float
    max_fsi: float
    setbacks: dict[str, float]
    permitted_uses: list[str]
    footprint_polygon: list[tuple[float, float]]
    parking_minimum: int | None = None
    bylaw_reference: str | None = None
    missing_middle: str | None = None


class SiteConstraints(BaseModel):
    parcel_id: str
    heritage_status: Literal["none", "listed", "designated"]
    tree_canopy_area_m2: float
    sun_shadow_rules: list[str]
    conservation_overlays: list[str]
    transit_distance_m: float
    easements: list[str]
    fire_station_distance_m: float | None = None


class Massing(BaseModel):
    massing_id: str
    height_m: float
    total_gfa_m2: float
    unit_mix: dict[str, int]
    retail_sqft: float
    affordable_units: int
    three_d_uri: str
    facade_renders: list[str]


class MassingOutput(BaseModel):
    options: list[Massing]


class FinancialModel(BaseModel):
    construction_cost: float
    projected_annual_rent: float
    projected_sale_price: float | None
    debt_service: float
    irr_5y: float
    irr_10y: float
    sensitivities: dict[str, dict[str, float]]


class Lever(BaseModel):
    change: str
    delta_probability: float


class VotePrediction(BaseModel):
    approval_probability: float
    per_councillor: dict[str, float]
    swing_councillors: list[str]
    levers: list[Lever]


class Letter(BaseModel):
    text: str
    inferred_concerns: list[str]
    source_neighborhood: str


class OppositionForecast(BaseModel):
    expected_letter_count: int
    sample_letters: list[Letter]
    top_concerns: dict[str, float]
    organized_groups: list[str]
    mitigations: list[str]


class GoNoGo(BaseModel):
    recommendation: Literal["buy", "pass", "conditional"]
    confidence: float
    developability_score: int = 0          # 0-100 composite headline score
    score_breakdown: dict[str, int] = {}   # explainable sub-scores
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


class AnalyzeRequest(BaseModel):
    parcel_id: str
    # Optional project overrides — when set, the brief evaluates *this* building
    # (not the auto-generated max-density massing). Powers the "adjust & re-run" UX.
    height_m: float | None = None
    total_units: int | None = None
    affordable_units: int | None = None
    retail_sqft: float | None = None

    def overrides(self) -> dict:
        o = {
            "height_m": self.height_m,
            "total_units": self.total_units,
            "affordable_units": self.affordable_units,
            "retail_sqft": self.retail_sqft,
        }
        return {k: v for k, v in o.items() if v is not None}
