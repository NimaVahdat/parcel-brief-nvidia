"""Solo demo CLI."""

import json

import typer

from opposition_generator.generate import generate
from opposition_generator.schemas import ProjectDescription

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def demo() -> None:
    """Generate a mock opposition forecast for a fake project."""
    project = ProjectDescription(
        height_m=42.0,
        total_units=84,
        affordable_units=0,
        use_mix={"residential": 0.85, "retail": 0.15},
        character_notes="brick mid-rise on Dundas Street West",
    )
    forecast = generate(project, neighborhood="Trinity-Bellwoods")
    print(json.dumps(forecast.model_dump(), indent=2))


if __name__ == "__main__":
    app()
