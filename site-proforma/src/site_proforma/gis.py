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

_CKAN_SEARCH = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"
ZONING_AREA_RID = "76a2620f-a6b4-495d-8e41-c0ede1f8a928"
HEIGHT_RID = "f0a88d06-2430-4025-b15d-362cabd00f31"

DATA_DIR = Path(os.getenv("SP_DATA_DIR", Path(__file__).resolve().parent.parent.parent / "data"))
ZONING_GEOJSON = DATA_DIR / "zoning_area.geojson"
HEIGHT_GEOJSON = DATA_DIR / "zoning_height.geojson"

_layers = None  # lazy cache: (za_tree, za_geoms, za_props, ht_tree, ht_geoms, ht_props)


def fetch_zoning() -> tuple[int, int]:
    """Download the two zoning layers to data/ via paginated datastore_search.

    Saves each as a GeoJSON FeatureCollection. Returns (n_area, n_height).
    """
    import httpx

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    counts = []
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        for rid, dest in ((ZONING_AREA_RID, ZONING_GEOJSON), (HEIGHT_RID, HEIGHT_GEOJSON)):
            features, offset = [], 0
            while True:
                r = c.get(_CKAN_SEARCH, params={"resource_id": rid, "limit": 1000, "offset": offset})
                r.raise_for_status()
                res = r.json()["result"]
                for rec in res["records"]:
                    geom = rec.pop("geometry", None)
                    if geom:
                        features.append({"geometry": geom, "properties": rec})
                offset += len(res["records"])
                if offset >= res.get("total", 0) or not res["records"]:
                    break
            dest.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
            counts.append(len(features))
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
            g = f.get("geometry")
            if not g:
                continue
            if isinstance(g, str):           # datastore returns geometry as a JSON string
                g = json.loads(g)
            try:
                geoms.append(shape(g))
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
        return float(v)
    except (TypeError, ValueError):
        return None


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    import math
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --------------------------------------------------------------------------- #
# Heritage Register — WGS84 address points (shapefile)
# --------------------------------------------------------------------------- #
HERITAGE_URL = ("https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
                "e41da515-5ad1-4bc3-85ea-18ec9e55cd33/resource/"
                "108b1080-d048-439f-a9e8-e8d6cd81bddb/download/"
                "heritage_register_address_points_wgs84.zip")
HERITAGE_DIR = DATA_DIR / "heritage"
_heritage = None  # list[(lon, lat, status)]


def fetch_heritage() -> int:
    import io
    import zipfile

    import httpx
    HERITAGE_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        r = c.get(HERITAGE_URL)
        r.raise_for_status()
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(HERITAGE_DIR)
    return len(list(HERITAGE_DIR.glob("*.shp")))


def _heritage_class(rec: dict) -> str:
    status = str(rec.get("STATUS") or "").lower()
    if rec.get("DESIGNATED") or "part iv" in status or "part v" in status or "designat" in status:
        return "designated"
    return "listed"


def _load_heritage() -> None:
    global _heritage
    shps = list(HERITAGE_DIR.glob("*.shp"))
    if not shps:
        _heritage = []
        return
    try:
        import shapefile  # pyshp
    except ImportError:
        _heritage = []
        return
    reader = shapefile.Reader(str(shps[0]))
    fields = [f[0] for f in reader.fields[1:]]
    pts = []
    for sr in reader.shapeRecords():
        if not sr.shape.points:
            continue
        lon, lat = sr.shape.points[0]
        pts.append((lon, lat, _heritage_class(dict(zip(fields, sr.record)))))
    _heritage = pts


def heritage_status(lat: float, lon: float, radius_m: float = 40.0) -> str:
    """Nearest heritage address point within radius -> its status, else 'none'."""
    global _heritage
    if _heritage is None:
        try:
            _load_heritage()
        except Exception:
            _heritage = []
    best, best_d = "none", radius_m
    for plon, plat, status in (_heritage or []):
        if abs(plat - lat) > 0.0006 or abs(plon - lon) > 0.0009:  # ~65 m prefilter
            continue
        d = _haversine_m(lat, lon, plat, plon)
        if d <= best_d:
            best_d, best = d, status
    return best


# --------------------------------------------------------------------------- #
# Property Boundaries — parcel footprints (GeoJSON polygons, WGS84)
# --------------------------------------------------------------------------- #
PARCELS_URL = ("https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
               "1acaa8b0-f235-4df6-8305-02025ccdeb07/resource/"
               "4d4943a6-98ec-4442-9ced-f600f5bc8d27/download/property-boundaries-4326.geojson")
PARCELS_GEOJSON = DATA_DIR / "property_boundaries.geojson"
_parcels = None  # (STRtree, geoms) | False


def fetch_parcels() -> int:
    """Download the ~314 MB Property Boundaries layer (streamed). Returns byte size."""
    import httpx
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=600, follow_redirects=True) as c:
        with c.stream("GET", PARCELS_URL) as r:
            r.raise_for_status()
            with PARCELS_GEOJSON.open("wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
    return PARCELS_GEOJSON.stat().st_size


def _load_parcels() -> None:
    global _parcels
    if not PARCELS_GEOJSON.exists():
        _parcels = False
        return
    try:
        from shapely.geometry import shape
        from shapely.strtree import STRtree
    except ImportError:
        _parcels = False
        return
    feats = json.loads(PARCELS_GEOJSON.read_text())["features"]
    geoms = []
    for f in feats:
        g = f.get("geometry")
        if not g:
            continue
        if isinstance(g, str):
            g = json.loads(g)
        try:
            geoms.append(shape(g))
        except Exception:
            continue
    _parcels = (STRtree(geoms), geoms)


def parcel_footprint(lat: float, lon: float) -> list | None:
    """Real parcel polygon containing the point -> [(lon,lat), ...], else None."""
    global _parcels
    if _parcels is None:
        try:
            _load_parcels()
        except Exception:
            _parcels = False
    if not _parcels:
        return None
    from shapely.geometry import Point
    tree, geoms = _parcels
    point = Point(lon, lat)
    for i in tree.query(point):
        g = geoms[int(i)]
        if g.covers(point):
            poly = g if g.geom_type == "Polygon" else max(g.geoms, key=lambda p: p.area)
            return [(round(x, 6), round(y, 6)) for x, y in poly.exterior.coords]
    return None
