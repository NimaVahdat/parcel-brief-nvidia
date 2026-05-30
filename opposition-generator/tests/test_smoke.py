"""Smoke test."""

from opposition_generator import generate
from opposition_generator.schemas import OppositionForecast, ProjectDescription


def test_generate_returns_forecast() -> None:
    project = ProjectDescription(
        height_m=30.0,
        total_units=50,
        affordable_units=10,
        use_mix={"residential": 1.0},
    )
    result = generate(project, neighborhood="Test-Neighborhood")
    assert isinstance(result, OppositionForecast)
    assert result.expected_letter_count > 0
    assert len(result.sample_letters) > 0
    assert len(result.top_concerns) > 0
