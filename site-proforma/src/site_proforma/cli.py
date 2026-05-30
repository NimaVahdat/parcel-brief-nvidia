"""Solo demo CLI."""

import json

import typer

from site_proforma.proforma import calculate
from site_proforma.schemas import Massing
from site_proforma.site import lookup

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("fetch-zoning")
def fetch_zoning_cmd() -> None:
    """Download the City Zoning By-law layers so lookup() returns real envelopes."""
    from site_proforma.gis import fetch_zoning

    n_area, n_height = fetch_zoning()
    print(f"Downloaded {n_area} zoning-area + {n_height} height-overlay polygons")


@app.command("fetch-heritage")
def fetch_heritage_cmd() -> None:
    """Download the Heritage Register so lookup() returns real heritage status."""
    from site_proforma.gis import fetch_heritage

    fetch_heritage()
    print("Downloaded heritage register")


@app.command("fetch-parcels")
def fetch_parcels_cmd() -> None:
    """Download Property Boundaries (~314 MB) for real parcel footprints."""
    from site_proforma.gis import fetch_parcels

    size = fetch_parcels()
    print(f"Downloaded property boundaries ({size / 1e6:.0f} MB)")


@app.command("fetch-fire")
def fetch_fire_cmd() -> None:
    """Download Fire Facility Locations for emergency-response proximity."""
    from site_proforma.gis import fetch_fire

    n = fetch_fire()
    print(f"Downloaded {n} fire stations")


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
