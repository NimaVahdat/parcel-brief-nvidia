"""Pydantic types. Mirrors docs/CONTRACTS.md."""

from pydantic import BaseModel


class ProjectDescription(BaseModel):
    height_m: float
    total_units: int
    affordable_units: int
    use_mix: dict[str, float]
    character_notes: str | None = None


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
