"""Pydantic types for vote-predictor. Mirrors docs/CONTRACTS.md."""

from pydantic import BaseModel


class ApplicationFeatures(BaseModel):
    parcel_id: str
    height_m: float
    total_units: int
    affordable_units: int
    retail_sqft: float
    use_mix: dict[str, float]
    neighborhood: str
    requested_variances: list[str] = []


class Lever(BaseModel):
    change: str
    delta_probability: float


class VotePrediction(BaseModel):
    approval_probability: float
    per_councillor: dict[str, float]
    swing_councillors: list[str]
    levers: list[Lever]
