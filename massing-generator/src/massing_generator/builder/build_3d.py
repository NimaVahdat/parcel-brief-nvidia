"""
Reconstruct a detailed 3D building from an LLM-generated JSON spec.

Reads a rich building/zoning description (lot, setbacks, massing, per-facade
windows/doors, roof, site features) and renders an interactive 3D model with
Plotly -> standalone HTML "UI".

Usage:
    python build_3d.py [spec.json] [-o out.html]

Coordinate frame:
    x = frontage (street width),  y = depth (front=0 -> rear),  z = up.
Front facade faces -y, rear faces +y, west = low x, east = high x.
"""

import argparse
import json
import math
import os

import numpy as np
import plotly.graph_objects as go

try:
    from .paths import OUTPUT_DIR, SPECS_DIR
except ImportError:  # running as a standalone script
    from paths import OUTPUT_DIR, SPECS_DIR


# ----------------------------------------------------------------------------
# low-level primitives
# ----------------------------------------------------------------------------
def box_mesh(x0, y0, z0, x1, y1, z1, color, opacity=1.0, name=""):
    """Axis-aligned box as a Mesh3d (8 verts, 12 triangles)."""
    xs = [x0, x1, x1, x0, x0, x1, x1, x0]
    ys = [y0, y0, y1, y1, y0, y0, y1, y1]
    zs = [z0, z0, z0, z0, z1, z1, z1, z1]
    i = [0, 0, 0, 0, 4, 4, 1, 1, 2, 2, 3, 3]
    j = [1, 2, 4, 7, 5, 6, 5, 6, 6, 7, 7, 4]
    k = [2, 3, 7, 4, 6, 7, 6, 2, 7, 3, 4, 0]
    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=i, j=j, k=k,
        color=color, opacity=opacity, flatshading=True,
        name=name, hoverinfo="name", showscale=False,
        lighting=dict(ambient=0.55, diffuse=0.85, specular=0.12, roughness=0.65),
        lightposition=dict(x=200, y=-400, z=500),
    )


def poly_mesh(pts, faces, color, opacity=1.0, name=""):
    """Arbitrary mesh from vertex list and triangle index list."""
    pts = np.asarray(pts, float)
    i = [f[0] for f in faces]
    j = [f[1] for f in faces]
    k = [f[2] for f in faces]
    return go.Mesh3d(
        x=pts[:, 0], y=pts[:, 1], z=pts[:, 2], i=i, j=j, k=k,
        color=color, opacity=opacity, flatshading=True,
        name=name, hoverinfo="name", showscale=False,
        lighting=dict(ambient=0.55, diffuse=0.85, specular=0.15, roughness=0.6),
        lightposition=dict(x=200, y=-400, z=500),
    )


def quad(p0, p1, p2, p3, color, opacity=1.0, name=""):
    """Flat quad (two triangles) from 4 corner points."""
    xs = [p[0] for p in (p0, p1, p2, p3)]
    ys = [p[1] for p in (p0, p1, p2, p3)]
    zs = [p[2] for p in (p0, p1, p2, p3)]
    return go.Mesh3d(
        x=xs, y=ys, z=zs, i=[0, 0], j=[1, 2], k=[2, 3],
        color=color, opacity=opacity, flatshading=True,
        name=name, hoverinfo="name", showscale=False,
    )


def box_edges(x0, y0, z0, x1, y1, z1, color="#5b5b5b", width=2, name=""):
    c = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (x0, y0, z1),
        (None, None, None),
        (x1, y0, z0), (x1, y0, z1), (None, None, None),
        (x1, y1, z0), (x1, y1, z1), (None, None, None),
        (x0, y1, z0), (x0, y1, z1),
    ]
    xs, ys, zs = zip(*c)
    return go.Scatter3d(
        x=xs, y=ys, z=zs, mode="lines", line=dict(color=color, width=width),
        hoverinfo="skip", showlegend=False, name=name,
    )


def cylinder(cx, cy, z0, z1, r, color, n=16, name=""):
    """Vertical cylinder (trunk / column)."""
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    bx, by = cx + r * np.cos(ang), cy + r * np.sin(ang)
    pts, faces = [], []
    for a in range(n):
        pts.append([bx[a], by[a], z0])
    for a in range(n):
        pts.append([bx[a], by[a], z1])
    for a in range(n):
        b = (a + 1) % n
        faces.append([a, b, n + b])
        faces.append([a, n + b, n + a])
    return poly_mesh(pts, faces, color, name=name)


def sphere(cx, cy, cz, r, color, n=10, name=""):
    """Low-poly sphere (tree canopy)."""
    u = np.linspace(0, math.pi, n)
    v = np.linspace(0, 2 * math.pi, n)
    uu, vv = np.meshgrid(u, v)
    x = cx + r * np.sin(uu) * np.cos(vv)
    y = cy + r * np.sin(uu) * np.sin(vv)
    z = cz + r * np.cos(uu)
    return go.Surface(
        x=x, y=y, z=z, showscale=False, opacity=1.0,
        colorscale=[[0, color], [1, color]], surfacecolor=np.zeros_like(x),
        hoverinfo="name", name=name, lighting=dict(ambient=0.6, diffuse=0.8),
    )


# ----------------------------------------------------------------------------
# facade openings (windows / doors as recessed panels on a wall plane)
# ----------------------------------------------------------------------------
def opening_on_face(face, x0, x1, y0, y1, cx, z_bot, w, h, color,
                    opacity=1.0, frame="#2a2a2a", name="Window"):
    """
    Place a rectangular opening on a named wall face.
    face in {front (-y), rear (+y), west (-x), east (+x)}.
    cx is the along-wall center fraction already converted to world coord.
    Returns [panel, frame] traces.
    """
    eps = 0.04
    if face == "front":
        y = y0 - eps
        p = [(cx - w / 2, y, z_bot), (cx + w / 2, y, z_bot),
             (cx + w / 2, y, z_bot + h), (cx - w / 2, y, z_bot + h)]
    elif face == "rear":
        y = y1 + eps
        p = [(cx - w / 2, y, z_bot), (cx + w / 2, y, z_bot),
             (cx + w / 2, y, z_bot + h), (cx - w / 2, y, z_bot + h)]
    elif face == "west":
        x = x0 - eps
        p = [(x, cx - w / 2, z_bot), (x, cx + w / 2, z_bot),
             (x, cx + w / 2, z_bot + h), (x, cx - w / 2, z_bot + h)]
    else:  # east
        x = x1 + eps
        p = [(x, cx - w / 2, z_bot), (x, cx + w / 2, z_bot),
             (x, cx + w / 2, z_bot + h), (x, cx - w / 2, z_bot + h)]
    panel = quad(*p, color, opacity=opacity, name=name)
    fr = go.Scatter3d(
        x=[q[0] for q in p] + [p[0][0]],
        y=[q[1] for q in p] + [p[0][1]],
        z=[q[2] for q in p] + [p[0][2]],
        mode="lines", line=dict(color=frame, width=4),
        hoverinfo="skip", showlegend=False)
    return [panel, fr]


# ----------------------------------------------------------------------------
# roofs
# ----------------------------------------------------------------------------
def hip_roof(x0, y0, x1, y1, z, pitch_deg, overhang, color):
    """Hip roof over a rectangular footprint."""
    ox0, oy0, ox1, oy1 = x0 - overhang, y0 - overhang, x1 + overhang, y1 + overhang
    span = min(ox1 - ox0, oy1 - oy0)
    rise = math.tan(math.radians(pitch_deg)) * span / 2
    # ridge runs along longer axis
    cx, cy = (ox0 + ox1) / 2, (oy0 + oy1) / 2
    inset = span / 2
    if (ox1 - ox0) >= (oy1 - oy0):
        r0 = (ox0 + inset, cy, z + rise)
        r1 = (ox1 - inset, cy, z + rise)
    else:
        r0 = (cx, oy0 + inset, z + rise)
        r1 = (cx, oy1 - inset, z + rise)
    e = [(ox0, oy0, z), (ox1, oy0, z), (ox1, oy1, z), (ox0, oy1, z)]  # 0..3
    pts = e + [r0, r1]                                                # 4,5
    faces = [(0, 1, 4), (1, 5, 4), (1, 2, 5), (2, 3, 5), (3, 0, 4), (3, 4, 5)]
    return poly_mesh(pts, faces, color, name="Roof (hip)"), (z + rise)


def gable_roof(x0, y0, x1, y1, z, pitch_deg, overhang, color):
    ox0, oy0, ox1, oy1 = x0 - overhang, y0 - overhang, x1 + overhang, y1 + overhang
    rise = math.tan(math.radians(pitch_deg)) * (ox1 - ox0) / 2
    cx = (ox0 + ox1) / 2
    pts = [(ox0, oy0, z), (ox1, oy0, z), (ox1, oy1, z), (ox0, oy1, z),
           (cx, oy0, z + rise), (cx, oy1, z + rise)]
    faces = [(0, 1, 4), (3, 2, 5), (1, 2, 5), (1, 5, 4), (0, 4, 5), (0, 5, 3)]
    return poly_mesh(pts, faces, color, name="Roof (gable)"), (z + rise)


def flat_roof(x0, y0, x1, y1, z, overhang, color):
    ox0, oy0, ox1, oy1 = x0 - overhang, y0 - overhang, x1 + overhang, y1 + overhang
    t = 0.3
    return box_mesh(ox0, oy0, z, ox1, oy1, z + t, color, name="Roof (flat)"), z + t


# ----------------------------------------------------------------------------
# main build
# ----------------------------------------------------------------------------
def build(spec):
    lot = spec["lot_details"]
    bs = spec["building_specifications"]
    sb = spec["setbacks_m"]
    ext = spec.get("exterior", {})
    roof = spec.get("roof", {})
    facades = spec.get("facades", {})
    site = spec.get("site", {})

    W = lot["lot_frontage_m"]
    D = lot["lot_depth_m"]
    height = bs["building_height_m"]
    storeys = int(bs["number_of_storeys"])
    coverage = bs["lot_coverage_percent"] / 100.0
    lot_area = lot["lot_area_sqm"]

    # setback envelope (front at y=0)
    x_west = sb["side_yard_west"]
    x_east = W - sb["side_yard_east"]
    y_front = sb["front_yard"]
    y_rear_limit = D - sb["rear_yard"]
    env_w = x_east - x_west

    foot_area = coverage * lot_area
    foot_depth = min(foot_area / env_w, y_rear_limit - y_front)
    x0, x1 = x_west, x_east
    y0, y1 = y_front, y_front + foot_depth

    fnd = ext.get("foundation_height_m", 0.0)
    wall_c = ext.get("wall_color", "#c8b6a0")
    accent_c = ext.get("accent_color", "#e8e2d5")
    trim_c = ext.get("trim_color", "#333")

    T = []  # traces

    # ----- ground & site -----
    grass = site.get("landscaping", {}).get("grass_color", "#7fb069")
    T.append(box_mesh(0, 0, -0.2, W, D, 0, "#8fae6e", name="Lot"))
    T.append(quad((0, 0, 0.02), (W, 0, 0.02), (W, y_front, 0.02),
                  (0, y_front, 0.02), grass, name="Front yard"))

    # driveway
    dv = site.get("driveway", {})
    if dv.get("present"):
        dw = dv.get("width_m", 3.0)
        dx0 = x0 if dv.get("side") == "west" else x1 - dw
        T.append(quad((dx0, 0, 0.03), (dx0 + dw, 0, 0.03),
                      (dx0 + dw, y_front, 0.03), (dx0, y_front, 0.03),
                      dv.get("color", "#9a9a9a"), name="Driveway"))

    # walkway front door -> street
    wk = site.get("walkway", {})
    if wk.get("present"):
        ww = wk.get("width_m", 1.2)
        door = facades.get("front", {}).get("door", {})
        wcx = x0 + door.get("position_frac", 0.5) * (x1 - x0)
        T.append(quad((wcx - ww / 2, 0, 0.03), (wcx + ww / 2, 0, 0.03),
                      (wcx + ww / 2, y_front, 0.03), (wcx - ww / 2, y_front, 0.03),
                      wk.get("color", "#b0a89c"), name="Walkway"))

    # fence
    fc = site.get("fence", {})
    if fc.get("present"):
        fh, fcol = fc.get("height_m", 1.8), fc.get("color", "#6b5b47")
        t = 0.05
        for s in fc.get("sides", []):
            if s == "east":
                T.append(box_mesh(W - t, 0, 0, W, D, fh, fcol, name="Fence"))
            elif s == "west":
                T.append(box_mesh(0, 0, 0, t, D, fh, fcol, name="Fence"))
            elif s == "rear":
                T.append(box_mesh(0, D - t, 0, W, D, fh, fcol, name="Fence"))

    # trees
    for tr in site.get("trees", []):
        tx, ty = tr["x_m"], tr["y_m"]
        th, cr = tr.get("height_m", 5.0), tr.get("canopy_r_m", 1.6)
        T.append(cylinder(tx, ty, 0, th * 0.55, 0.18, "#6b4a2b", name="Tree"))
        T.append(sphere(tx, ty, th * 0.55 + cr * 0.6, cr, "#4f8b3b", name="Tree"))

    # ----- foundation -----
    if fnd > 0:
        T.append(box_mesh(x0, y0, 0, x1, y1, fnd,
                          ext.get("foundation_color", "#7d7d7d"), name="Foundation"))

    # ----- massing (main block + optional L wing) -----
    base_z = fnd
    blocks = [(x0, y0, x1, y1, height)]  # main full footprint
    massing = spec.get("massing", {})
    if massing.get("footprint_shape") == "L":
        wing = massing["wing"]
        ww = (x1 - x0) * wing.get("width_frac", 0.45)
        wd = (y1 - y0) * wing.get("depth_frac", 0.5)
        wh = wing.get("height_m", height)
        # cut main block depth, add a lower wing at rear on chosen side
        main_depth = (y1 - y0) - wd
        blocks = [(x0, y0, x1, y0 + main_depth, height)]
        if wing.get("side") == "east":
            blocks.append((x1 - ww, y0 + main_depth, x1, y1, wh))
        else:
            blocks.append((x0, y0 + main_depth, x0 + ww, y1, wh))

    for (bx0, by0, bx1, by1, bh) in blocks:
        T.append(box_mesh(bx0, by0, base_z, bx1, by1, bh, wall_c, name="Building"))
        T.append(box_edges(bx0, by0, base_z, bx1, by1, bh, color=trim_c, width=2))

    # storey lines on main block front face
    mbx0, mby0, mbx1, mby1, mbh = blocks[0]
    for s in range(1, storeys):
        z = base_z + (mbh - base_z) * s / storeys
        T.append(go.Scatter3d(
            x=[x0, x1, x1, x0, x0], y=[y0, y0, y1, y1, y0], z=[z] * 5,
            mode="lines", line=dict(color=accent_c, width=4),
            hoverinfo="skip", showlegend=False, name="Floor line"))

    # ----- facade openings -----
    glass = "#8fc7e8"

    def storey_z(level, sill, h):
        sh = (height - base_z) / storeys
        return base_z + (level - 1) * sh + sill, h

    face_extent = {
        "front": (x0, x1), "rear": (x0, x1),
        "west": (y0, y1), "east": (y0, y1),
    }
    for face, fdata in facades.items():
        lo, hi = face_extent[face]
        for win in fdata.get("windows", []):
            cx = lo + win["position_frac"] * (hi - lo)
            zb, h = storey_z(win["storey"], win.get("sill_m", 1.0), win["height_m"])
            T += opening_on_face(face, x0, x1, y0, y1, cx, zb,
                                 win["width_m"], h, glass, opacity=0.8, name="Window")
        door = fdata.get("door")
        if door:
            cx = lo + door["position_frac"] * (hi - lo)
            T += opening_on_face(face, x0, x1, y0, y1, cx, base_z,
                                 door["width_m"], door["height_m"],
                                 door.get("color", "#5b3a21"), name="Door")

    # ----- front porch -----
    porch = facades.get("front", {}).get("porch", {})
    if porch.get("present"):
        pd = porch.get("depth_m", 1.8)
        pw = (x1 - x0) * porch.get("width_frac", 0.55)
        ph = porch.get("height_m", 2.6)
        pcx = (x0 + x1) / 2
        px0, px1 = pcx - pw / 2, pcx + pw / 2
        py0, py1 = y0 - pd, y0
        T.append(box_mesh(px0, py0, base_z, px1, py1, base_z + 0.15, "#cfc4b0",
                          name="Porch floor"))
        # porch roof
        T.append(box_mesh(px0, py0 - 0.1, ph, px1, py1, ph + 0.15, accent_c,
                          name="Porch roof"))
        ncol = porch.get("columns", 2)
        for cdex in range(ncol):
            cxp = px0 + (cdex + 0.5) * pw / ncol
            T.append(cylinder(cxp, py0 + 0.15, base_z, ph, 0.1, accent_c,
                              name="Porch column"))

    # ----- rear balcony -----
    bal = facades.get("rear", {}).get("balcony", {})
    if bal.get("present"):
        sh = (height - base_z) / storeys
        bz = base_z + (bal.get("storey", 2) - 1) * sh
        bw = (x1 - x0) * bal.get("width_frac", 0.4)
        bcx = x0 + bal.get("position_frac", 0.5) * (x1 - x0)
        bd = bal.get("depth_m", 1.5)
        bx0_, bx1_ = bcx - bw / 2, bcx + bw / 2
        T.append(box_mesh(bx0_, y1, bz, bx1_, y1 + bd, bz + 0.12, "#b8a98f",
                          name="Balcony"))
        # railing
        T.append(box_edges(bx0_, y1, bz + 0.12, bx1_, y1 + bd, bz + 1.0,
                           color=trim_c, width=3))

    # ----- roof on main block -----
    rtype = roof.get("type", "hip")
    pitch = roof.get("pitch_deg", 30)
    oh = roof.get("overhang_m", 0.4)
    rcol = roof.get("color", "#41484f")
    if rtype == "hip":
        rmesh, ridge = hip_roof(mbx0, mby0, mbx1, mby1, mbh, pitch, oh, rcol)
    elif rtype == "gable":
        rmesh, ridge = gable_roof(mbx0, mby0, mbx1, mby1, mbh, pitch, oh, rcol)
    else:
        rmesh, ridge = flat_roof(mbx0, mby0, mbx1, mby1, mbh, oh, rcol)
    T.append(rmesh)
    # lower wing flat-ish roof
    for (bx0, by0, bx1, by1, bh) in blocks[1:]:
        rm, _ = flat_roof(bx0, by0, bx1, by1, bh, oh * 0.5, rcol)
        T.append(rm)

    # chimney
    ch = roof.get("chimney", {})
    if ch.get("present"):
        cw = ch.get("width_m", 0.9)
        ctop = ridge + ch.get("height_above_ridge_m", 1.2)
        cxp = (mbx0 + cw) if ch.get("side") == "west" else (mbx1 - cw - 0.3)
        cyp = (mby0 + mby1) / 2
        T.append(box_mesh(cxp, cyp - cw / 2, mbh, cxp + cw, cyp + cw / 2, ctop,
                          "#8a5a44", name="Chimney"))

    # dormers (front slope)
    for dm in roof.get("dormers", []):
        if dm.get("face") != "front":
            continue
        dw = dm.get("width_m", 1.6)
        dh = dm.get("height_m", 1.3)
        dcx = mbx0 + dm.get("position_frac", 0.5) * (mbx1 - mbx0)
        dz = mbh + 0.2
        T.append(box_mesh(dcx - dw / 2, mby0 - oh + 0.1, dz,
                          dcx + dw / 2, mby0 + 0.6, dz + dh, accent_c,
                          name="Dormer"))
        # dormer window
        T += opening_on_face("front", dcx - dw / 2, dcx + dw / 2,
                             mby0 - oh + 0.1, mby0 + 0.6, dcx, dz + 0.2,
                             dw * 0.6, dh * 0.6, glass, opacity=0.8, name="Dormer window")

    return T, dict(W=W, D=D, ridge=ridge)


def make_figure(spec):
    traces, dims = build(spec)
    fig = go.Figure(data=traces)
    name = spec.get("project_name", "Building")
    bs = spec["building_specifications"]
    subtitle = (f"{bs.get('architectural_style','')} {bs['building_type']} | "
                f"{bs['number_of_storeys']} storeys | {bs['building_height_m']} m | "
                f"GFA {bs['gross_floor_area_sqm']} m² | coverage {bs['lot_coverage_percent']}%")
    fig.update_layout(
        title=dict(text=f"<b>{name}</b><br><sup>{subtitle}</sup>", x=0.5),
        scene=dict(
            xaxis=dict(title="Frontage (m)", backgroundcolor="#eef3f8"),
            yaxis=dict(title="Depth (m)", backgroundcolor="#eef3f8"),
            zaxis=dict(title="Height (m)", backgroundcolor="#f7f9fc"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.7, y=-1.9, z=1.0)),
        ),
        paper_bgcolor="#ffffff",
        margin=dict(l=0, r=0, t=70, b=0),
        legend=dict(orientation="h", y=-0.02),
        showlegend=True,
    )
    return fig


def main():
    ap = argparse.ArgumentParser()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ap.add_argument("spec", nargs="?", default=os.path.join(SPECS_DIR, "discription_building.json"))
    ap.add_argument("-o", "--out", default=os.path.join(OUTPUT_DIR, "building_3d.html"))
    args = ap.parse_args()
    with open(args.spec) as f:
        spec = json.load(f)
    fig = make_figure(spec)
    fig.write_html(args.out, include_plotlyjs="cdn", auto_open=False)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
