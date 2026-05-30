"""Forecast subpackage: turn retrieved deputations into an OppositionForecast."""

from __future__ import annotations

from opposition_generator.forecast.aggregate import (
    aggregate_concerns,
    aggregate_groups,
    build_mitigations,
    estimate_letter_count,
)
from opposition_generator.forecast.letters import generate_sample_letters
from opposition_generator.index.retrieve import Retrieved
from opposition_generator.schemas import OppositionForecast, ProjectDescription


def build_forecast(
    project: ProjectDescription,
    neighborhood: str,
    retrieved: list[Retrieved],
) -> tuple[OppositionForecast, bool]:
    """Assemble the full OppositionForecast from retrieved real deputations.

    Returns (forecast, used_llm). The four structured fields are aggregated from the
    real retrieved letters; only sample_letters involves generation.
    """
    top_concerns = aggregate_concerns(retrieved)
    groups = aggregate_groups(retrieved)
    count = estimate_letter_count(retrieved, project)
    mitigations = build_mitigations(top_concerns)
    sample_letters, used_llm = generate_sample_letters(project, neighborhood, retrieved)

    forecast = OppositionForecast(
        expected_letter_count=count,
        sample_letters=sample_letters,
        top_concerns=top_concerns,
        organized_groups=groups,
        mitigations=mitigations,
    )
    return forecast, used_llm


__all__ = ["build_forecast"]
