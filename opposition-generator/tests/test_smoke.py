"""Smoke test — generate() returns a valid forecast even with no index / no Ollama.

With nothing indexed and Ollama unreachable, generate() must still return a valid
OppositionForecast via the heuristic degradation tier (it must never raise).
"""

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
    # concern scores are normalized into [0, 1]
    assert all(0.0 <= v <= 1.0 for v in result.top_concerns.values())


def test_generate_never_raises_on_zero_affordable() -> None:
    project = ProjectDescription(
        height_m=80.0,
        total_units=300,
        affordable_units=0,
        use_mix={"residential": 0.9, "retail": 0.1},
    )
    result = generate(project, neighborhood="Anywhere")
    assert result.expected_letter_count > 0
    assert "affordability" in result.top_concerns
