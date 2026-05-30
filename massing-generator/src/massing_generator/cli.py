"""Solo demo CLI."""

import json
from pathlib import Path
from typing import Annotated

import typer

from massing_generator.generate import generate
from massing_generator.schemas import ZoningEnvelope

app = typer.Typer(no_args_is_help=True, add_completion=False)

_DEMO_ENVELOPE = ZoningEnvelope(
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


@app.command()
def demo() -> None:
    """Generate mock massings for a fake envelope (no LLM, no render)."""
    output = generate(_DEMO_ENVELOPE, use_mock=True)
    print(json.dumps(output.model_dump(), indent=2))


@app.command()
def build(
    raw: Annotated[
        Path | None,
        typer.Argument(
            help="Zoning brief JSON (ZoningEnvelope shape). Omit for the demo envelope."
        ),
    ] = None,
    num_options: Annotated[
        int, typer.Option(help="Design variants to generate (each is one LLM call).")
    ] = 1,
    no_render: Annotated[
        bool, typer.Option(help="Skip the 3D render; emit metadata only.")
    ] = False,
) -> None:
    """Run the real engine: brief -> LLM spec -> validate -> 3D render. Needs ANTHROPIC_API_KEY."""
    envelope = ZoningEnvelope.model_validate_json(raw.read_text()) if raw else _DEMO_ENVELOPE
    output = generate(envelope, num_options=num_options, use_mock=False, render=not no_render)
    print(json.dumps(output.model_dump(), indent=2))


@app.command()
def render(
    spec: Annotated[Path, typer.Argument(help="Building-spec JSON to render.")],
    mode: Annotated[str, typer.Option(help="hq | normal | blueprint | plotly")] = "hq",
    glb: Annotated[bool, typer.Option(help="Also export a glTF/GLB model (slower).")] = False,
) -> None:
    """Render an existing building spec to 3D (offline — no LLM call)."""
    from massing_generator.builder import pipeline

    data = json.loads(spec.read_text())
    art = pipeline.render_spec(data, spec.stem, mode=mode, glb=glb)
    print(json.dumps(art.__dict__, indent=2))


@app.command()
def validate(
    spec: Annotated[Path, typer.Argument(help="Building-spec JSON to validate.")],
) -> None:
    """Run the geometric/structural validator on a building spec."""
    from massing_generator.builder import validate_building as vb

    data = json.loads(spec.read_text())
    report = vb.validate(data)
    report.print()
    raise typer.Exit(code=1 if report.count(vb.ERROR) else 0)


if __name__ == "__main__":
    app()
