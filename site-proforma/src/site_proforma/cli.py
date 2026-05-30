"""Solo demo CLI."""

import json

import typer

from site_proforma.proforma import calculate
from site_proforma.schemas import Massing
from site_proforma.site import lookup

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def lookup_cmd(parcel_id: str = typer.Option("543-dundas-w", "--parcel-id")) -> None:
    """Print mock site data for a parcel."""
    site = lookup(parcel_id)
    print(json.dumps(site.model_dump(), indent=2))


@app.command()
def proforma(demo: bool = typer.Option(False, "--demo")) -> None:
    """Run a mock pro-forma."""
    site = lookup("543-dundas-w")
    massing = Massing(
        massing_id="demo-tall",
        height_m=42.0,
        total_gfa_m2=6000.0,
        unit_mix={"studio": 12, "1br": 30, "2br": 28, "3br": 14},
        retail_sqft=2400,
        affordable_units=0,
        three_d_uri="mock://demo.glb",
        facade_renders=[],
    )
    model = calculate(massing, site)
    print(json.dumps(model.model_dump(), indent=2))


if __name__ == "__main__":
    app()
