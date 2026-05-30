"""Deterministic, envelope-respecting massing geometry/program.

The SDXL/ControlNet 3D rendering (controlnet.py) produces the *visuals*; this module
produces the *numbers* — GFA, height, unit mix, retail, affordable — that must (a)
fit the legal envelope (height <= max_height_m, GFA <= max_fsi x lot_area) and (b) be
internally consistent (units match GFA), so the downstream pro-forma is realistic.

Lot area is computed from the real parcel footprint (site-proforma now returns the
actual Property Boundaries polygon); a sane default is used if the footprint is the
fallback square.
"""

from __future__ import annotations

import math

SQFT_PER_SQM = 10.7639
FLOOR_TO_FLOOR_M = 3.1
COVERAGE = 0.55           # share of lot the floor plate occupies
AVG_UNIT_GFA_M2 = 85.0    # incl. circulation/common
_UNIT_RATIOS = {"studio": 0.15, "1br": 0.45, "2br": 0.30, "3br": 0.10}


def lot_area_m2(footprint_polygon: list) -> float:
    """Shoelace area of a WGS84 (lon, lat) ring, in m² (local equirectangular)."""
    pts = footprint_polygon or []
    if len(pts) < 4:
        return 0.0
    lat0 = sum(p[1] for p in pts) / len(pts)
    mlat = 111_320.0
    mlon = 111_320.0 * math.cos(math.radians(lat0))
    proj = [(p[0] * mlon, p[1] * mlat) for p in pts]
    area = 0.0
    for (x1, y1), (x2, y2) in zip(proj, proj[1:]):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _unit_mix(total_units: int) -> dict[str, int]:
    mix = {k: int(total_units * r) for k, r in _UNIT_RATIOS.items()}
    mix["1br"] += total_units - sum(mix.values())  # remainder into 1br
    return {k: v for k, v in mix.items() if v > 0}


def fit_massing(
    *, max_height_m: float, max_fsi: float, lot_area: float,
    has_retail: bool, gfa_fraction: float, affordable_share: float,
) -> dict:
    """Return a consistent {height_m, total_gfa_m2, unit_mix, retail_sqft,
    affordable_units} that respects the height and FSI caps."""
    floorplate = max(lot_area * COVERAGE, 250.0)
    fsi_cap_gfa = max_fsi * lot_area
    max_floors = max(1, int(max_height_m / FLOOR_TO_FLOOR_M))

    target_gfa = gfa_fraction * fsi_cap_gfa
    floors = min(max_floors, max(1, math.ceil(target_gfa / floorplate)))
    gfa = min(floors * floorplate, fsi_cap_gfa)
    height = round(min(max_height_m, floors * FLOOR_TO_FLOOR_M), 1)

    retail_m2 = floorplate if has_retail else 0.0   # one ground-floor retail level
    res_gfa = max(gfa - retail_m2, 0.0)
    units = max(1, round(res_gfa / AVG_UNIT_GFA_M2))
    affordable = int(round(units * affordable_share))

    return {
        "height_m": height,
        "total_gfa_m2": round(gfa, 0),
        "unit_mix": _unit_mix(units),
        "retail_sqft": round(retail_m2 * SQFT_PER_SQM, 0),
        "affordable_units": affordable,
    }
