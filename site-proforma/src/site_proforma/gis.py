"""Real zoning lookup from the City of Toronto Zoning By-law 569-2013 open data.

Two spatial layers (downloaded once to data/, gitignored):
  * Zoning Area     — zone category (ZN_ZONE), total FSI (FSI_TOTAL)
  * Height Overlay  — max height in metres (HT_LABEL)

`lookup_envelope(lat, lon)` does point-in-polygon on both (shapely + STRtree) and
returns a real ZoningEnvelope, or None if the data isn't present / the point isn't
covered — in which case site.py falls back to its location heuristic. Per the City:
geometry must be read with the by-law text, so where an attribute is unspecified
(-1) we fill a sensible default for that zone category.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from site_proforma.schemas import ZoningEnvelope

_CKAN_DUMP = "https://ckan0.cf.opendata.inter.prod-toronto.ca/datastore/dump/%s?format=geojson"
ZONING_AREA_RID = "76a2620f-a6b4-495d-8e41-c0ede1f8a928"
HEIGHT_RID = "f0a88d06-2430-4025-b15d-362cabd00f31"

DATA_DIR = Path(os.getenv("SP_DATA_DIR", Path(__file__).resolve().parent.parent.parent / "data"))
ZONING_GEOJSON = DATA_DIR / "zoning_area.geojson"
HEIGHT_GEOJSON = DATA_DIR / "zoning_height.geojson"

_layers = None  # lazy cache: (za_tree, za_geoms, za_props, ht_tree, ht_geoms, ht_props)


def fetch_zoning() -> tuple[int, int]:
    """Download the two zoning GeoJSON layers to data/. Returns (n_area, n_height)."""
    import httpx

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    counts = []
    for rid, dest in ((ZONING_AREA_RID, ZONING_GEOJSON), (HEIGHT_RID, HEIGHT_GEOJSON)):
        with httpx.Client(timeout=300, follow_redirects=True) as c:
            r = c.get(_CKAN_DUMP % rid)
            r.raise_for_status()
            dest.write_bytes(r.content)
        counts.append(len(json.loads(dest.read_text()).get("features", [])))
    return tuple(counts)  # type: ignore[return-value]


def _build():
    global _layers
    if not (ZONING_GEOJSON.exists() and HEIGHT_GEOJSON.exists()):
        _layers = False
        return
    try:
        from shapely.geometry import shape
        from shapely.strtree import STRtree
    except ImportError:
        _layers = False
        return

    def load(path):
        feats = json.loads(path.read_text())["features"]
        geoms, props = [], []
        for f in feats:
            if not f.get("geometry"):
                continue
            try:
                geoms.append(shape(f["geometry"]))
                props.append(f.get("properties", {}))
            except Exception:
                continue
        return STRtree(geoms), geoms, props

    za_tree, za_geoms, za_props = load(ZONING_GEOJSON)
    ht_tree, ht_geoms, ht_props = load(HEIGHT_GEOJSON)
    _layers = (za_tree, za_geoms, za_props, ht_tree, ht_geoms, ht_props)


def _hit(point, tree, geoms, props) -> dict | None:
    for i in tree.query(point):
        i = int(i)
        if geoms[i].covers(point):
            return props[i]
    return None


def _uses(zn: str) -> list[str]:
    z = (zn or "").upper()
    if z.startswith("CR"):
        return ["residential", "retail", "office"]
    if z.startswith("C"):
        return ["retail", "office"]
    if z.startswith("R"):
        return ["residential"]
    if z.startswith("E"):
        return ["office", "industrial"]
    if z.startswith("I"):
        return ["institutional"]
    return ["residential"]


def _default_fsi(zn: str) -> float:
    z = (zn or "").upper()
    if z.startswith(("CR", "RA")):
        return 3.0
    if z.startswith("C"):
        return 3.0
    if z.startswith(("RD", "RS", "RT")):
        return 0.6
    if z.startswith("R"):
        return 1.0
    return 1.0


def lookup_envelope(parcel_id: str, lat: float, lon: float) -> ZoningEnvelope | None:
    """Real envelope from the zoning layers, or None if unavailable/uncovered."""
    global _layers
    if _layers is None:
        _build()
    if not _layers:
        return None

    from shapely.geometry import Point

    point = Point(lon, lat)
    za_tree, za_geoms, za_props, ht_tree, ht_geoms, ht_props = _layers
    za = _hit(point, za_tree, za_geoms, za_props)
    if za is None:
        return None

    zn = za.get("ZN_ZONE", "")
    fsi_raw = _num(za.get("FSI_TOTAL"))
    max_fsi = fsi_raw if fsi_raw and fsi_raw > 0 else _default_fsi(zn)

    ht = _hit(point, ht_tree, ht_geoms, ht_props)
    ht_raw = _num(ht.get("HT_LABEL")) if ht else None
    max_height = ht_raw if ht_raw and ht_raw > 0 else round(max(11.0, max_fsi * 7.0), 1)

    z = (zn or "").upper()
    parking = 1 if z.startswith(("RD", "RS", "RT")) else 0
    # ~20 m square footprint around the point (real parcel geometry is a separate layer)
    dlat, dlon = 0.00009, 0.00012
    poly = [(lon - dlon, lat - dlat), (lon - dlon, lat + dlat),
            (lon + dlon, lat + dlat), (lon + dlon, lat - dlat), (lon - dlon, lat - dlat)]
    return ZoningEnvelope(
        parcel_id=parcel_id, max_height_m=float(max_height), max_fsi=float(max_fsi),
        setbacks={"north": 3.0, "south": 0.0, "east": 1.5, "west": 1.5},
        permitted_uses=_uses(zn), footprint_polygon=poly, parking_minimum=parking,
    )


def _num(v) -> float | None:
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None
