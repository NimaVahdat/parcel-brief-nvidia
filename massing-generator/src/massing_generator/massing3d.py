"""Clean, deterministic 3D massing — instant, no LLM, no VTK.

Builds a presentable mixed-use massing (retail base → podium → setback tower) directly
from the legal envelope + the massing numbers, and renders it as a self-contained
interactive Plotly HTML scene. This replaces the slow LLM-spec path for the live brief:
every option gets a clean 3D in milliseconds, deterministically.

Coordinate frame: x = frontage (m), y = depth (m), z = height (m), centred on the lot.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

FLOOR_TO_FLOOR_M = 3.1
_SQFT_PER_SQM = 10.7639

# where rendered HTML scenes are written (gitignored); the connector serves this at /massing
RENDERS_DIR = Path(
    os.getenv("MASSING_RENDERS_DIR", Path(__file__).resolve().parent.parent.parent / "data" / "renders")
)


def render_to_uri(envelope, massing, basename: str) -> str | None:
    """Render the massing to RENDERS_DIR/<basename>.html; return the '/massing/..' URL path."""
    try:
        RENDERS_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", basename).strip("-") or "massing"
        out = RENDERS_DIR / f"{safe}.html"
        render(envelope, massing, str(out))
        return f"/massing/{safe}.html"
    except Exception:
        return None

# palette
_GROUND = "#e8ecf1"
_RETAIL = "#c9a36b"      # warm stone base
_PODIUM = "#cfd6de"      # light masonry
_TOWER = "#7fa8d4"       # glass blue
_EDGE = "#33415c"


def _lot_dims_m(footprint_polygon: list) -> tuple[float, float]:
    """Frontage x depth (m) from the WGS84 footprint bounding box."""
    pts = footprint_polygon or []
    if len(pts) < 3:
        return 28.0, 36.0
    lats = [p[1] for p in pts]
    lons = [p[0] for p in pts]
    lat0 = sum(lats) / len(lats)
    w = (max(lons) - min(lons)) * 111_320.0 * math.cos(math.radians(lat0))
    d = (max(lats) - min(lats)) * 111_320.0
    # clamp to sane dev-parcel dims
    return max(12.0, min(w, 200.0)), max(12.0, min(d, 200.0))


def _box(x0, y0, z0, x1, y1, z1, color, opacity, name):
    import plotly.graph_objects as go

    xs = [x0, x1, x1, x0, x0, x1, x1, x0]
    ys = [y0, y0, y1, y1, y0, y0, y1, y1]
    zs = [z0, z0, z0, z0, z1, z1, z1, z1]
    return go.Mesh3d(
        x=xs, y=ys, z=zs,
        i=[0, 0, 0, 0, 4, 4, 1, 1, 2, 2, 3, 3],
        j=[1, 2, 4, 7, 5, 6, 5, 6, 6, 7, 7, 4],
        k=[2, 3, 7, 4, 6, 7, 6, 2, 7, 3, 4, 0],
        color=color, opacity=opacity, flatshading=True, name=name,
        hoverinfo="name", showscale=False,
        lighting=dict(ambient=0.6, diffuse=0.85, specular=0.18, roughness=0.55),
        lightposition=dict(x=180, y=-360, z=520),
    )


def _floor_lines(x0, y0, z0, x1, y1, z1, n):
    """Thin horizontal banding around a box to read as storeys."""
    import plotly.graph_objects as go

    if n <= 0:
        return None
    xs, ys, zs = [], [], []
    for i in range(1, n + 1):
        z = z0 + (z1 - z0) * i / (n + 1)
        ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0), (None, None)]
        for x, y in ring:
            xs.append(x); ys.append(y); zs.append(None if x is None else z)
    return go.Scatter3d(x=xs, y=ys, z=zs, mode="lines",
                        line=dict(color=_EDGE, width=1.5), hoverinfo="skip", showlegend=False)


def make_figure(envelope, massing):
    """Deterministic Plotly massing from the envelope + massing numbers."""
    import plotly.graph_objects as go

    lot_w, lot_d = _lot_dims_m(envelope.footprint_polygon)
    sb = envelope.setbacks or {}
    # buildable plate after setbacks (front/back on depth, sides on frontage)
    bw = max(8.0, lot_w - (sb.get("east", 1.5) + sb.get("west", 1.5)))
    bd = max(8.0, lot_d - (sb.get("north", 3.0) + sb.get("south", 0.0)))
    height = float(massing.height_m)
    floors = max(1, round(height / FLOOR_TO_FLOOR_M))
    has_retail = massing.retail_sqft and massing.retail_sqft > 0

    cx, cy = lot_w / 2, lot_d / 2
    x0, x1 = cx - bw / 2, cx + bw / 2
    y0, y1 = cy - bd / 2, cy + bd / 2

    traces = []
    # ground / lot
    traces.append(_box(0, 0, -0.4, lot_w, lot_d, 0, _GROUND, 1.0, "Lot"))

    z = 0.0
    # retail base (one taller ground storey)
    if has_retail:
        rh = 4.5
        traces.append(_box(x0, y0, z, x1, y1, rh, _RETAIL, 1.0, "Retail base"))
        z = rh
        floors = max(1, floors - 1)

    podium_floors = min(floors, 4) if height > 24 else floors
    tower_floors = floors - podium_floors
    podium_top = z + podium_floors * FLOOR_TO_FLOOR_M

    traces.append(_box(x0, y0, z, x1, y1, podium_top, _PODIUM, 1.0, "Podium"))
    fl = _floor_lines(x0, y0, z, x1, y1, podium_top, podium_floors)
    if fl:
        traces.append(fl)

    if tower_floors > 0:
        # tower stepped back ~30% on each side
        sx, sy = bw * 0.18, bd * 0.18
        tx0, tx1 = x0 + sx, x1 - sx
        ty0, ty1 = y0 + sy, y1 - sy
        tower_top = podium_top + tower_floors * FLOOR_TO_FLOOR_M
        traces.append(_box(tx0, ty0, podium_top, tx1, ty1, tower_top, _TOWER, 0.92, "Tower"))
        fl = _floor_lines(tx0, ty0, podium_top, tx1, ty1, tower_top, tower_floors)
        if fl:
            traces.append(fl)

    fig = go.Figure(data=traces)
    rng = max(lot_w, lot_d, height) * 1.1
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            aspectmode="data",
            camera=dict(eye=dict(x=1.5, y=-1.7, z=1.1)),
            bgcolor="white",
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white",
        showlegend=False,
    )
    return fig


def render(envelope, massing, out_html: str) -> str:
    """Render the massing to a standalone HTML file; returns the path."""
    fig = make_figure(envelope, massing)
    fig.write_html(out_html, include_plotlyjs="cdn", auto_open=False,
                   config={"displmodebar": False})
    return out_html
