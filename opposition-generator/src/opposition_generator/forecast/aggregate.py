"""Turn retrieved real deputations into the grounded forecast fields.

Everything here is computed from the *real* retrieved letters, not generated — so
`top_concerns`, `organized_groups`, `expected_letter_count`, and `mitigations` are
defensible aggregations of what residents actually wrote. Only `sample_letters`
(in forecast/letters.py) involves generation.
"""

from __future__ import annotations

from collections import defaultdict

from opposition_generator.forecast.taxonomy import (
    CONCERN_MITIGATIONS,
    canonical_group,
    mitigation_for,
)
from opposition_generator.index.retrieve import Retrieved
from opposition_generator.schemas import ProjectDescription


def aggregate_concerns(retrieved: list[Retrieved]) -> dict[str, float]:
    """Similarity-weighted frequency of concern tags, normalized to [0, 1].

    A concern's weight is the sum of retrieval scores of letters that raise it,
    divided by the total retrieval score — so concerns from more-relevant letters
    count for more. Falls back to plain frequency if scores are all zero.
    """
    weight: dict[str, float] = defaultdict(float)
    total = 0.0
    use_score = any(r.score > 0 for r in retrieved)
    for r in retrieved:
        w = r.score if use_score else 1.0
        total += w
        for concern in set(r.deputation.concerns):
            weight[concern] += w
    if total <= 0:
        return {}
    ranked = sorted(weight.items(), key=lambda kv: -kv[1])
    return {concern: round(w / total, 2) for concern, w in ranked}


def aggregate_groups(retrieved: list[Retrieved]) -> list[str]:
    """Organizing groups ranked by how often they appear, alias-normalized."""
    counts: dict[str, int] = defaultdict(int)
    for r in retrieved:
        for g in r.deputation.groups:
            if g.strip():
                counts[canonical_group(g)] += 1
    return [g for g, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def _project_sensitivity(project: ProjectDescription) -> float:
    """A 0.6-1.8 multiplier: taller, denser, less-affordable projects draw more fire."""
    factor = 1.0
    if project.height_m >= 60:
        factor += 0.5
    elif project.height_m >= 35:
        factor += 0.25
    if project.total_units >= 200:
        factor += 0.3
    elif project.total_units >= 80:
        factor += 0.15
    affordable_share = (
        project.affordable_units / project.total_units if project.total_units else 0.0
    )
    if affordable_share == 0:
        factor += 0.2
    elif affordable_share >= 0.2:
        factor -= 0.2
    return max(0.6, min(1.8, factor))


def estimate_letter_count(
    retrieved: list[Retrieved], project: ProjectDescription
) -> int:
    """Heuristic expected deputation volume.

    Baseline scales with how much similar opposition we retrieved (a proxy for how
    contentious this kind of project is in this area), adjusted by project
    sensitivity. Deliberately simple and explainable; a calibrated regression on
    real (features -> volume) pairs is a later upgrade.
    """
    base = 8 + 3 * len(retrieved)  # more relevant past opposition -> larger baseline
    same_hood = sum(1 for r in retrieved if r.same_neighborhood)
    base += 2 * same_hood
    return int(round(base * _project_sensitivity(project)))


def build_mitigations(top_concerns: dict[str, float], limit: int = 4) -> list[str]:
    """Map the dominant concerns to actionable, project-specific mitigations."""
    mitigations: list[str] = []
    for concern in list(top_concerns.keys())[:limit]:
        if concern in CONCERN_MITIGATIONS:
            mitigations.append(mitigation_for(concern))
    if not mitigations:
        mitigations.append(mitigation_for("affordability"))
    return mitigations
