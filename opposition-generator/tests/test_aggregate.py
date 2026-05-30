"""Offline tests for taxonomy normalization and forecast aggregation."""

from opposition_generator.forecast.aggregate import (
    aggregate_concerns,
    aggregate_groups,
    estimate_letter_count,
)
from opposition_generator.forecast.taxonomy import (
    canonical_group,
    normalize_concerns,
)
from opposition_generator.index.retrieve import Retrieved
from opposition_generator.index.store import Deputation
from opposition_generator.schemas import ProjectDescription


def _retrieved(concerns, groups, score=1.0, same=True) -> Retrieved:
    dep = Deputation(
        deputation_id="x",
        neighborhood="Trinity-Bellwoods",
        text="…",
        concerns=concerns,
        groups=groups,
    )
    return Retrieved(deputation=dep, score=score, same_neighborhood=same)


def test_normalize_concerns_maps_synonyms() -> None:
    assert normalize_concerns(["Overshadowing", "congestion", "tall"]) == [
        "shadow",
        "traffic",
        "height",
    ]


def test_normalize_concerns_dedupes() -> None:
    assert normalize_concerns(["shadow", "sunlight", "shadowing"]) == ["shadow"]


def test_canonical_group_collapses_variants() -> None:
    a = canonical_group("Trinity Bellwoods Residents Assoc.")
    b = canonical_group("Trinity Bellwoods Residents Association")
    assert a == b == "Trinity Bellwoods Residents Association"


def test_aggregate_concerns_normalized_and_ranked() -> None:
    retrieved = [
        _retrieved(["shadow", "traffic"], []),
        _retrieved(["shadow"], []),
        _retrieved(["heritage"], []),
    ]
    concerns = aggregate_concerns(retrieved)
    assert all(0.0 <= v <= 1.0 for v in concerns.values())
    # shadow appears most often -> ranked first
    assert list(concerns)[0] == "shadow"


def test_aggregate_groups_ranked_by_frequency() -> None:
    retrieved = [
        _retrieved([], ["Friends of Trinity-Bellwoods"]),
        _retrieved([], ["Friends of Trinity-Bellwoods"]),
        _retrieved([], ["Annex Residents Association"]),
    ]
    groups = aggregate_groups(retrieved)
    assert groups[0] == "Friends of Trinity-Bellwoods"


def test_aggregate_groups_filters_corporate_noise() -> None:
    retrieved = [
        _retrieved([], ["Liberty Village Residents Association"]),
        _retrieved([], ["939923 Ontario Limited"]),
        _retrieved([], ["Allied Properties REIT"]),
        _retrieved([], ["Toronto and East York Community Council"]),
    ]
    groups = aggregate_groups(retrieved)
    assert groups == ["Liberty Village Residents Association"]


def test_letter_count_scales_with_sensitivity() -> None:
    retrieved = [_retrieved(["shadow"], []) for _ in range(5)]
    tall_no_affordable = ProjectDescription(
        height_m=90, total_units=300, affordable_units=0, use_mix={"residential": 1.0}
    )
    small_affordable = ProjectDescription(
        height_m=12, total_units=20, affordable_units=8, use_mix={"residential": 1.0}
    )
    assert estimate_letter_count(retrieved, tall_no_affordable) > estimate_letter_count(
        retrieved, small_affordable
    )
