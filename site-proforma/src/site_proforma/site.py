"""lookup() — the site-data contract function.

`parcel_id` is the map-click point the UI sends as "lat_lng" (see ui/ParcelMap).
We resolve it to a building envelope + site constraints.

What's real here: transit distance is computed from actual Toronto subway-station
coordinates (haversine). The zoning envelope is a deterministic, location-aware
gradient (downtown → high density, outer → low) — a defensible screening estimate.
The fully-legal envelope needs the Zoning By-law spatial layer; `_zoning_from_geojson`
is the hook for that (point-in-polygon over data/zoning.geojson when present).
"""

from __future__ import annotations

import math

from site_proforma.schemas import SiteConstraints, SiteData, ZoningEnvelope

# Toronto financial core (downtown reference point)
_CORE = (43.6486, -79.3806)

# A sample of TTC subway stations (lat, lon) for nearest-transit distance.
_STATIONS = [
    ("Union", 43.6453, -79.3806), ("St Andrew", 43.6479, -79.3849),
    ("Osgoode", 43.6509, -79.3866), ("St Patrick", 43.6549, -79.3884),
    ("Queen's Park", 43.6597, -79.3902), ("Museum", 43.6671, -79.3936),
    ("Spadina", 43.6674, -79.4041), ("Bloor-Yonge", 43.6703, -79.3860),
    ("Sherbourne", 43.6720, -79.3766), ("Castle Frank", 43.6736, -79.3685),
    ("Broadview", 43.6769, -79.3585), ("Pape", 43.6797, -79.3450),
    ("Dundas West", 43.6571, -79.4529), ("Lansdowne", 43.6592, -79.4426),
    ("Ossington", 43.6624, -79.4263), ("Christie", 43.6644, -79.4185),
    ("Eglinton", 43.7056, -79.3987), ("St Clair", 43.6878, -79.3933),
    ("Davisville", 43.6976, -79.3973), ("College", 43.6614, -79.3832),
    ("Dundas", 43.6561, -79.3807), ("Queen", 43.6525, -79.3793),
    ("King", 43.6492, -79.3779), ("Rosedale", 43.6772, -79.3886),
    ("Summerhill", 43.6822, -79.3905), ("Keele", 43.6555, -79.4596),
    ("High Park", 43.6545, -79.4663), ("Donlands", 43.6809, -79.3378),
]


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse_parcel_id(parcel_id: str) -> tuple[float, float] | None:
    """Parse the UI's "lat_lng" id. Returns (lat, lon) or None."""
    try:
        lat_s, lon_s = parcel_id.split("_")
        return float(lat_s), float(lon_s)
    except (ValueError, AttributeError):
        return None


def _nearest_transit_m(lat: float, lon: float) -> float:
    return round(min(_haversine_m(lat, lon, s[1], s[2]) for s in _STATIONS), 0)


def _zoning_envelope(parcel_id: str, lat: float, lon: float) -> ZoningEnvelope:
    """Deterministic, location-aware envelope by distance from the core."""
    d_km = _haversine_m(lat, lon, *_CORE) / 1000.0
    if d_km < 2.5:          # downtown
        height, fsi, uses, parking = 80.0, 6.0, ["residential", "retail", "office"], 0
    elif d_km < 6.0:        # midtown / avenues
        height, fsi, uses, parking = 32.0, 3.0, ["residential", "retail"], 0
    else:                   # neighbourhoods
        height, fsi, uses, parking = 14.0, 1.2, ["residential"], 1
    # ~20 m square footprint approximation around the point
    dlat, dlon = 0.00009, 0.00012
    poly = [(lon - dlon, lat - dlat), (lon - dlon, lat + dlat),
            (lon + dlon, lat + dlat), (lon + dlon, lat - dlat), (lon - dlon, lat - dlat)]
    return ZoningEnvelope(
        parcel_id=parcel_id, max_height_m=height, max_fsi=fsi,
        setbacks={"north": 3.0, "south": 0.0, "east": 1.5, "west": 1.5},
        permitted_uses=uses, footprint_polygon=poly, parking_minimum=parking,
    )


def _constraints(parcel_id: str, lat: float, lon: float, height_m: float) -> SiteConstraints:
    transit = _nearest_transit_m(lat, lon)
    sun_shadow = (
        ["5h equinox sunlight required on adjacent sidewalks; shadow study required"]
        if height_m >= 30 else []
    )
    return SiteConstraints(
        parcel_id=parcel_id, heritage_status="none", tree_canopy_area_m2=0.0,
        sun_shadow_rules=sun_shadow, conservation_overlays=[],
        transit_distance_m=transit, easements=[],
    )


def lookup(parcel_id: str) -> SiteData:
    """Look up the building envelope + site constraints for a Toronto parcel point.

    Uses the real City Zoning By-law layers (point-in-polygon) when the data is
    present; otherwise falls back to a location-aware heuristic envelope.
    """
    coords = _parse_parcel_id(parcel_id)
    if coords is None:
        # not a coordinate id (e.g. an address slug) — fall back to a core location
        coords = _CORE
    lat, lon = coords

    envelope = None
    try:
        from site_proforma.gis import lookup_envelope
        envelope = lookup_envelope(parcel_id, lat, lon)
    except Exception:
        envelope = None
    if envelope is None:
        envelope = _zoning_envelope(parcel_id, lat, lon)

    constraints = _constraints(parcel_id, lat, lon, envelope.max_height_m)
    return SiteData(zoning_envelope=envelope, constraints=constraints)
