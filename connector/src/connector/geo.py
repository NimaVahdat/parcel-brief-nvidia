"""Parcel -> neighbourhood + ward resolution for the orchestrator.

The connector receives `parcel_id` as the UI's map-click point ("lat_lng"). The
community + approvals agents need the real neighbourhood (for opposition) and ward
councillor context (for the vote prediction) — that's an orchestration concern, so
it lives here rather than changing any component contract.

Backed by City of Toronto open data (Neighbourhoods + City Wards, ~183 small
polygons total) via point-in-polygon. Downloaded once to data/ (gitignored);
graceful fallback to a default when data/shapely are absent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_SEARCH = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"
NEIGHBOURHOODS_RID = "5e6095fc-1bef-4776-887c-28d37f722c51"
WARDS_RID = "7672dac5-b383-4d7c-90ec-291dc69d37bf"

DATA_DIR = Path(os.getenv("CONNECTOR_DATA_DIR", Path(__file__).resolve().parent.parent.parent / "data"))
NBHD_GEOJSON = DATA_DIR / "neighbourhoods.geojson"
WARDS_GEOJSON = DATA_DIR / "wards.geojson"

DEFAULT_NEIGHBOURHOOD = "Toronto"
_layers = None  # ((nbhd_tree, nbhd_geoms, nbhd_props), (ward_tree, ...)) | False


def fetch_layers() -> tuple[int, int]:
    """Download the neighbourhood + ward layers (small). Returns (n_nbhd, n_ward)."""
    import httpx

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    counts = []
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        for rid, dest in ((NEIGHBOURHOODS_RID, NBHD_GEOJSON), (WARDS_RID, WARDS_GEOJSON)):
            features, offset = [], 0
            while True:
                r = c.get(_SEARCH, params={"resource_id": rid, "limit": 1000, "offset": offset})
                r.raise_for_status()
                res = r.json()["result"]
                for rec in res["records"]:
                    geom = rec.pop("geometry", None)
                    if isinstance(geom, str):
                        geom = json.loads(geom)
                    if geom:
                        features.append({"geometry": geom, "properties": rec})
                offset += len(res["records"])
                if offset >= res.get("total", 0) or not res["records"]:
                    break
            dest.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
            counts.append(len(features))
    return tuple(counts)  # type: ignore[return-value]


def _load_one(path: Path):
    from shapely.geometry import shape
    from shapely.strtree import STRtree

    feats = json.loads(path.read_text())["features"]
    geoms, props = [], []
    for f in feats:
        g = f.get("geometry")
        if isinstance(g, str):
            g = json.loads(g)
        if not g:
            continue
        try:
            geoms.append(shape(g))
            props.append(f.get("properties", {}))
        except Exception:
            continue
    return STRtree(geoms), geoms, props


def _build() -> None:
    global _layers
    if not (NBHD_GEOJSON.exists() and WARDS_GEOJSON.exists()):
        _layers = False
        return
    try:
        _layers = (_load_one(NBHD_GEOJSON), _load_one(WARDS_GEOJSON))
    except Exception:
        _layers = False


def _hit(point, layer) -> dict | None:
    tree, geoms, props = layer
    for i in tree.query(point):
        i = int(i)
        if geoms[i].covers(point):
            return props[i]
    return None


def _parse(parcel_id: str):
    try:
        lat, lon = parcel_id.split("_")
        return float(lat), float(lon)
    except (ValueError, AttributeError):
        return None


def resolve_context(parcel_id: str) -> dict:
    """Return {neighbourhood, ward, ward_name, councillors} for a parcel point.

    Always returns a usable dict (defaults when data/shapely unavailable).
    """
    coords = _parse(parcel_id)
    out = {"neighbourhood": DEFAULT_NEIGHBOURHOOD, "ward": None, "ward_name": None,
           "councillors": ["Local Councillor"]}
    if coords is None:
        return out

    global _layers
    if _layers is None:
        _build()
    if not _layers:
        return out

    try:
        from shapely.geometry import Point
    except ImportError:
        return out
    point = Point(coords[1], coords[0])  # (lon, lat)
    nbhd, wards = _layers

    n = _hit(point, nbhd)
    if n and n.get("AREA_NAME"):
        out["neighbourhood"] = n["AREA_NAME"]
    w = _hit(point, wards)
    if w:
        out["ward"] = w.get("AREA_SHORT_CODE")
        out["ward_name"] = w.get("AREA_NAME")
        if out["ward"] and out["ward_name"]:
            out["councillors"] = [f"Ward {int(out['ward'])} – {out['ward_name']}"]
    return out


if __name__ == "__main__":  # python -m connector.geo  -> download the layers
    print("fetched (neighbourhoods, wards):", fetch_layers())
