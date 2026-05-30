"""Solo demo CLI."""

import json

import typer

from site_proforma.proforma import calculate
from site_proforma.schemas import Massing
from site_proforma.site import lookup

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("lookup")
def lookup_cmd(parcel_id: str = typer.Option("43.6532_-79.3832", "--parcel-id")) -> None:
    """Look up the site envelope + constraints for a parcel (UI lat_lng point)."""
    site = lookup(parcel_id)
    print(json.dumps(site.model_dump(), indent=2))


@app.command()
def proforma(parcel_id: str = typer.Option("43.6532_-79.3832", "--parcel-id")) -> None:
    """Run the pro-forma for a sample massing on the looked-up site."""
    site = lookup(parcel_id)
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
