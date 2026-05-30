"""generate() — THE CONTRACT.

Forecast community opposition for a Toronto development project, grounded in the
real TMMIS deputation record via the retrieve -> forecast pipeline.

Graceful degradation (the connector must never crash because of this component):

    full RAG        retrieval + LLM-generated grounded letters   (mode="rag")
        │ LLM down
    retrieval-only  real retrieved data, templated letters       (mode="retrieval")
        │ store/embeddings down
    heuristic       sensible mock from project params alone       (mode="heuristic")

`generate()` returns the contract type `OppositionForecast` in all cases.
`generate_with_meta()` exposes which tier ran (used by the CLI/service for debug).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from opposition_generator.forecast import build_forecast
from opposition_generator.index.retrieve import retrieve
from opposition_generator.schemas import Letter, OppositionForecast, ProjectDescription

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    forecast: OppositionForecast
    mode: str  # "rag" | "retrieval" | "heuristic"
    retrieved_count: int


def _project_query(project: ProjectDescription, neighborhood: str) -> str:
    affordable_share = (
        project.affordable_units / project.total_units if project.total_units else 0.0
    )
    uses = ", ".join(f"{k} {v:.0%}" for k, v in project.use_mix.items())
    notes = f" {project.character_notes}" if project.character_notes else ""
    return (
        f"Proposed {project.height_m:.0f}m development in {neighborhood}, Toronto: "
        f"{project.total_units} units, {affordable_share:.0%} affordable, uses: {uses}.{notes}"
    )


def generate_with_meta(
    project: ProjectDescription, neighborhood: str
) -> ForecastResult:
    """Run the pipeline and report which degradation tier produced the result."""
    query = _project_query(project, neighborhood)

    try:
        retrieved = retrieve(query, neighborhood)
    except Exception as exc:  # store/embeddings entirely unavailable
        logger.warning("retrieval failed (%s); falling back to heuristic", exc)
        return ForecastResult(_heuristic_forecast(project, neighborhood), "heuristic", 0)

    if not retrieved:
        logger.info("no deputations retrieved; using heuristic forecast")
        return ForecastResult(_heuristic_forecast(project, neighborhood), "heuristic", 0)

    forecast, used_llm = build_forecast(project, neighborhood, retrieved)
    mode = "rag" if used_llm else "retrieval"
    return ForecastResult(forecast, mode, len(retrieved))


def generate(project: ProjectDescription, neighborhood: str) -> OppositionForecast:
    """Forecast community opposition for a Toronto development project.

    See module docstring for the degradation tiers. Always returns a valid
    OppositionForecast (never raises) so the connector pipeline stays alive.
    """
    try:
        return generate_with_meta(project, neighborhood).forecast
    except Exception as exc:  # absolute backstop
        logger.error("generate() failed unexpectedly (%s); returning heuristic", exc)
        return _heuristic_forecast(project, neighborhood)


def _heuristic_forecast(
    project: ProjectDescription, neighborhood: str
) -> OppositionForecast:
    """Project-parameter-only fallback when retrieval is unavailable."""
    from opposition_generator.forecast.aggregate import _project_sensitivity
    from opposition_generator.forecast.taxonomy import mitigation_for

    affordable_share = (
        project.affordable_units / project.total_units if project.total_units else 0.0
    )
    concerns: dict[str, float] = {"shadow": 0.6, "character": 0.5, "traffic": 0.4}
    if affordable_share == 0:
        concerns["affordability"] = 0.7
    if project.height_m >= 35:
        concerns["height"] = 0.65

    ranked = dict(sorted(concerns.items(), key=lambda kv: -kv[1]))
    count = int(round(30 * _project_sensitivity(project)))
    letter = Letter(
        text=(
            f"As a long-time resident of {neighborhood}, I am writing to oppose the "
            f"proposed {project.height_m:.0f}m development. It raises concerns about "
            f"{', '.join(list(ranked)[:3])}, and as proposed does not fit our community."
        ),
        inferred_concerns=list(ranked)[:3],
        source_neighborhood=neighborhood,
    )
    return OppositionForecast(
        expected_letter_count=count,
        sample_letters=[letter],
        top_concerns=ranked,
        organized_groups=[f"{neighborhood} Residents Association"],
        mitigations=[mitigation_for(c) for c in list(ranked)[:3]],
    )
