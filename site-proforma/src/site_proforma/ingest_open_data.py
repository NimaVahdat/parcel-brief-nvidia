"""Toronto Open Data → PostGIS.

Downloads zoning, parcels, heritage, trees, TTC GTFS, TRCA. Loads each as a
PostGIS table indexed on `geom`.

TODO:
- Use `requests` against the open.toronto.ca CKAN API (or direct GeoJSON URLs).
- For each layer: download, read with geopandas, write with .to_postgis.
- Create GiST indexes on geom columns.
- Normalize column names to snake_case.
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def ingest_all() -> None:
    """Run every open-data ingest in sequence."""
    raise NotImplementedError("Implement Open Data → PostGIS. See docs/DATA.md for URLs.")


def ingest_zoning() -> None:
    raise NotImplementedError


def ingest_parcels() -> None:
    raise NotImplementedError


def ingest_heritage() -> None:
    raise NotImplementedError


def ingest_trees() -> None:
    raise NotImplementedError


def ingest_transit_gtfs() -> None:
    raise NotImplementedError


def ingest_trca() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    ingest_all()
