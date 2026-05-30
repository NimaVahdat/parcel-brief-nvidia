"""Solo demo CLI."""

import json

import typer

from massing_generator.generate import generate
from massing_generator.schemas import ZoningEnvelope

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def demo() -> None:
    """Generate mock massings for a fake envelope."""
    envelope = ZoningEnvelope(
        parcel_id="543-dundas-w",
        max_height_m=42.0,
        max_fsi=4.0,
        setbacks={"north": 3.0, "south": 0.0, "east": 1.5, "west": 1.5},
        permitted_uses=["residential", "retail"],
        footprint_polygon=[
            (-79.418, 43.649),
            (-79.418, 43.650),
            (-79.417, 43.650),
            (-79.417, 43.649),
            (-79.418, 43.649),
        ],
        parking_minimum=0,
    )
    output = generate(envelope)
    print(json.dumps(output.model_dump(), indent=2))


if __name__ == "__main__":
    app()
