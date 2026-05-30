"""Pydantic types. Mirrors docs/CONTRACTS.md."""

from pydantic import BaseModel


class ZoningEnvelope(BaseModel):
    parcel_id: str
    max_height_m: float
    max_fsi: float
    setbacks: dict[str, float]
    permitted_uses: list[str]
    footprint_polygon: list[tuple[float, float]]
    parking_minimum: int | None = None


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
