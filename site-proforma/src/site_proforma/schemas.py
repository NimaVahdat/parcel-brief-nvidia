"""Pydantic types. Mirrors docs/CONTRACTS.md."""

from typing import Literal

from pydantic import BaseModel


class ZoningEnvelope(BaseModel):
    parcel_id: str
    max_height_m: float
    max_fsi: float
    setbacks: dict[str, float]
    permitted_uses: list[str]
    footprint_polygon: list[tuple[float, float]]
    parking_minimum: int | None = None


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
    unit_mix: dict[str, int]
    retail_sqft: float
    affordable_units: int
    three_d_uri: str
    facade_renders: list[str]


class FinancialModel(BaseModel):
    construction_cost: float
    projected_annual_rent: float
    projected_sale_price: float | None
    debt_service: float
    irr_5y: float
    irr_10y: float
    sensitivities: dict[str, dict[str, float]]
