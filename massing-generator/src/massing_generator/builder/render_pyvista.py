"""
Realistic 3D building renderer (PyVista / VTK) from the LLM JSON spec.

Quality modes:
    --mode normal      flat solid-color massing (fast, matches the Plotly style)
    --mode hq          procedural PBR textures (grass, brick, shingle, wood, ...)
    --mode blueprint   X-ray / blueprint aesthetic: translucent fills + cyan wireframe

Outputs an interactive standalone HTML (vtk.js) and optional PNG screenshot.

Usage:
    python render_pyvista.py [spec.json] --mode hq -o building_hq.html
    python render_pyvista.py --mode both        # writes normal + hq
    python render_pyvista.py --mode blueprint   # writes building_blueprint.html

Coordinate frame: x = frontage, y = depth (front=0 -> rear), z = up.
"""

import argparse
import json
import math
import os

import numpy as np
import pyvista as pv

try:
    from . import textures as tx
    from .paths import OUTPUT_DIR, SPECS_DIR, TEXTURES_DIR
except ImportError:  # running as a standalone script
    import textures as tx
    from paths import OUTPUT_DIR, SPECS_DIR, TEXTURES_DIR

TEX_DIR = TEXTURES_DIR


# ----------------------------------------------------------------------------
# material registry: name -> texture file + PBR + fallback flat color
# ----------------------------------------------------------------------------
MATERIALS = {
    "grass":    dict(tex="grass",    color="#7fb069", rough=0.95, metal=0.0, tile=2.5),
    "dirt":     dict(tex="dirt",     color="#8a6a46", rough=1.0,  metal=0.0, tile=3.0),
    "concrete": dict(tex="concrete", color="#9a9a9a", rough=0.9,  metal=0.0, tile=2.0),
    "paver":    dict(tex="concrete", color="#b0a89c", rough=0.85, metal=0.0, tile=1.0),
    "brick":    dict(tex="brick",    color="#a35a45", rough=0.9,  metal=0.0, tile=1.5),
    "stucco":   dict(tex="stucco",   color="#e8e2d5", rough=0.85, metal=0.0, tile=2.0),
    "shingle":  dict(tex="shingle",  color="#41484f", rough=0.8,  metal=0.0, tile=1.4),
    "wood":     dict(tex="wood",     color="#7a5a34", rough=0.7,  metal=0.0, tile=1.0),
    "bark":     dict(tex="bark",     color="#5a4230", rough=1.0,  metal=0.0, tile=0.6),
    "glass":    dict(tex=None,       color="#aee0f5", rough=0.05, metal=0.9, tile=1.0, opacity=0.4),
    "metal":    dict(tex=None,       color="#888d92", rough=0.3,  metal=1.0, tile=1.0),
    "trim":     dict(tex=None,       color="#f2efe8", rough=0.6,  metal=0.0, tile=1.0),
    "stone":    dict(tex=None,       color="#c9c2b4", rough=0.8,  metal=0.0, tile=1.0),
    "interior": dict(tex=None,       color="#0e1216", rough=1.0,  metal=0.0, tile=1.0),
    # --- tower / curtain-wall materials ---
    "granite":  dict(tex=None,       color="#3a3a3a", rough=0.55, metal=0.0, tile=1.0),
    "spandrel": dict(tex=None,       color="#41586c", rough=0.4,  metal=0.1, tile=1.0),
    "mullion":  dict(tex=None,       color="#33333d", rough=0.4,  metal=0.5, tile=1.0),
    "glasscw":  dict(tex=None,       color="#cfe6f4", rough=0.04, metal=0.9, tile=1.0, opacity=0.62),
    "membrane": dict(tex=None,       color="#8a8a8a", rough=0.85, metal=0.0, tile=1.0),
    "panel":    dict(tex=None,       color="#3a4a5a", rough=0.5,  metal=0.3, tile=1.0),
    "gold":     dict(tex=None,       color="#c0a060", rough=0.3,  metal=0.7, tile=1.0),
}
_TEX_CACHE = {}

# ----------------------------------------------------------------------------
# blueprint / X-ray palette
# ----------------------------------------------------------------------------
_BP_BG    = "#030d1a"    # near-black navy background
_BP_EDGE  = "#00d4ff"    # primary cyan wireframe
_BP_GLOW  = "#80eeff"    # brighter cyan for glass
_BP_FILL  = "#061420"    # almost-black fill tint
_BP_GROUND_MATS = {"grass", "dirt", "paver", "concrete"}


def _add_blueprint_mesh(pl, mesh, matname):
    """Render one mesh in blueprint/X-ray style (double-pass: fill + wireframe)."""
    if matname == "_shadow":
        return
    if matname == "_canopy":
        pl.add_mesh(mesh, color=_BP_EDGE, opacity=0.3,
                    style="wireframe", line_width=1.0, lighting=False)
        return
    is_ground = matname in _BP_GROUND_MATS
    is_glass  = matname in ("glass", "glasscw")
    fill_op   = 0.04 if is_ground else (0.22 if is_glass else 0.10)
    edge_col  = "#003a50" if is_ground else (_BP_GLOW if is_glass else _BP_EDGE)
    edge_op   = 0.22 if is_ground else 0.90
    lw        = 0.6 if is_ground else 1.5
    # pass 1: translucent volume fill
    pl.add_mesh(mesh, color=_BP_FILL, opacity=fill_op, lighting=False, show_edges=False)
    # pass 2: glowing wireframe overlay
    pl.add_mesh(mesh, color=edge_col, opacity=edge_op,
                style="wireframe", line_width=lw, lighting=False)


def get_texture(name):
    if name not in _TEX_CACHE:
        t = pv.read_texture(os.path.join(TEX_DIR, f"{name}.png"))
        t.repeat = True
        _TEX_CACHE[name] = t
    return _TEX_CACHE[name]


# ----------------------------------------------------------------------------
# geometry primitives -> pv.PolyData
# ----------------------------------------------------------------------------
def quad(p0, p1, p2, p3, tu=1.0, tv=1.0):
    pts = np.array([p0, p1, p2, p3], float)
    mesh = pv.PolyData(pts, faces=[4, 0, 1, 2, 3])
    mesh.active_texture_coordinates = np.array(
        [[0, 0], [tu, 0], [tu, tv], [0, tv]], float)
    return mesh


def box(x0, y0, z0, x1, y1, z1, tile=1.5, cap_top=True):
    """Box as separate textured wall quads (+ top). Bottom skipped."""
    lx, ly, lz = x1 - x0, y1 - y0, z1 - z0
    faces = [
        quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), lx / tile, lz / tile),
        quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), lx / tile, lz / tile),
        quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), ly / tile, lz / tile),
        quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), ly / tile, lz / tile),
    ]
    if cap_top:
        faces.append(quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
                          lx / tile, ly / tile))
    return faces


def poly(pts, faces):
    flat = []
    for f in faces:
        flat.append(len(f)); flat.extend(f)
    return pv.PolyData(np.asarray(pts, float), faces=flat)


# ----------------------------------------------------------------------------
# facade-local frame: place detailed components on any wall face
# ----------------------------------------------------------------------------
def face_basis(face, mbx0, mby0, mbx1, mby1, cx):
    """Return (P0, U, N): wall point at along-wall center cx, in-wall axis, outward."""
    if face == "front":
        return np.array([cx, mby0, 0.]), np.array([1, 0, 0.]), np.array([0, -1, 0.])
    if face == "rear":
        return np.array([cx, mby1, 0.]), np.array([1, 0, 0.]), np.array([0, 1, 0.])
    if face == "west":
        return np.array([mbx0, cx, 0.]), np.array([0, 1, 0.]), np.array([-1, 0, 0.])
    return np.array([mbx1, cx, 0.]), np.array([0, 1, 0.]), np.array([1, 0, 0.])


def local_box(P0, U, N, u0, u1, v0, v1, n0, n1):
    """Box in the wall-local (u along wall, v=height, n outward) frame."""
    def w(u, v, n):
        return P0 + U * u + np.array([0, 0, v]) + N * n
    combos = [(u0, v0, n0), (u1, v0, n0), (u1, v1, n0), (u0, v1, n0),
              (u0, v0, n1), (u1, v0, n1), (u1, v1, n1), (u0, v1, n1)]
    pts = [w(*c) for c in combos]
    faces = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4],
             [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return poly(pts, faces)


def local_quad(P0, U, N, u0, u1, v0, v1, n):
    def w(u, v):
        return P0 + U * u + np.array([0, 0, v]) + N * n
    return quad(w(u0, v0), w(u1, v0), w(u1, v1), w(u0, v1))


def add_window(s, face, mbx0, mby0, mbx1, mby1, cx, zb, w, h, sill=True):
    """Framed, mullioned, recessed glass window on a wall face."""
    P0, U, N = face_basis(face, mbx0, mby0, mbx1, mby1, cx)
    ft = 0.09            # frame thickness
    gp = 0.02            # glass proud offset (wall is solid, no opening cut,
                         # so a recessed pane would hide behind the brick)
    u0, u1 = -w / 2, w / 2
    # white frame (top / bottom / left / right), slightly proud of wall
    s.add(local_box(P0, U, N, u0 - ft, u1 + ft, zb + h, zb + h + ft, -0.02, 0.05), "trim")
    s.add(local_box(P0, U, N, u0 - ft, u1 + ft, zb - ft, zb, -0.02, 0.05), "trim")
    s.add(local_box(P0, U, N, u0 - ft, u0, zb, zb + h, -0.02, 0.05), "trim")
    s.add(local_box(P0, U, N, u1, u1 + ft, zb, zb + h, -0.02, 0.05), "trim")
    # opaque dark interior just proud of the brick so the wall texture does
    # not read through the glass — reads as an empty/dark room behind the pane
    s.add(local_quad(P0, U, N, u0, u1, zb, zb + h, gp - 0.012), "interior")
    # glass set just proud of the interior so it reads in front of the brick
    s.add(local_quad(P0, U, N, u0, u1, zb, zb + h, gp), "glass")
    # mullion bars (thin, just in front of glass)
    s.add(local_box(P0, U, N, -0.03, 0.03, zb, zb + h, gp + 0.01, gp + 0.04), "trim")
    s.add(local_box(P0, U, N, u0, u1, zb + h / 2 - 0.03, zb + h / 2 + 0.03,
                    gp + 0.01, gp + 0.04), "trim")
    # stone sill protruding below
    if sill:
        s.add(local_box(P0, U, N, u0 - 0.12, u1 + 0.12, zb - 0.12, zb, 0.0, 0.16), "stone")


def add_door(s, face, mbx0, mby0, mbx1, mby1, cx, base_z, w, h):
    P0, U, N = face_basis(face, mbx0, mby0, mbx1, mby1, cx)
    ft = 0.1
    u0, u1 = -w / 2, w / 2
    # frame
    s.add(local_box(P0, U, N, u0 - ft, u1 + ft, base_z + h, base_z + h + ft, -0.02, 0.06), "trim")
    s.add(local_box(P0, U, N, u0 - ft, u0, base_z, base_z + h, -0.02, 0.06), "trim")
    s.add(local_box(P0, U, N, u1, u1 + ft, base_z, base_z + h, -0.02, 0.06), "trim")
    # door slab set just proud of the wall (solid wall, no cut opening) + handle
    s.add(local_box(P0, U, N, u0, u1, base_z, base_z + h, 0.0, 0.04), "wood")
    s.add(local_box(P0, U, N, u1 - 0.18, u1 - 0.1, base_z + h * 0.45,
                    base_z + h * 0.55, 0.04, 0.09), "metal")


def add_tree(s, tx, ty, th, cr):
    """Clustered irregular canopy + tapered trunk + ground shadow disc."""
    trunk = pv.Cylinder(center=(tx, ty, th * 0.27), direction=(0, 0, 1),
                        radius=0.17, height=th * 0.55, resolution=14)
    s.add(trunk, "bark", map_plane=True, plane_tiles=2.0)
    base_z = th * 0.55 + cr * 0.5
    blobs = [(0, 0, 0.05, cr), (cr*0.55, 0, cr*0.2, cr*0.7),
             (-cr*0.5, cr*0.4, cr*0.25, cr*0.65), (cr*0.15, -cr*0.5, cr*0.5, cr*0.6),
             (0, 0, cr*0.7, cr*0.7)]
    for dx, dy, dz, r in blobs:
        s.add(pv.Sphere(radius=r, center=(tx + dx, ty + dy, base_z + dz),
                        theta_resolution=18, phi_resolution=18), "_canopy")
    # soft contact shadow on ground
    disc = pv.Disc(center=(tx, ty, 0.03), inner=0, outer=cr * 1.1,
                   normal=(0, 0, 1), r_res=1, c_res=24)
    s.add(disc, "_shadow")


def hip_roof(x0, y0, x1, y1, z, pitch, oh):
    ox0, oy0, ox1, oy1 = x0 - oh, y0 - oh, x1 + oh, y1 + oh
    span = min(ox1 - ox0, oy1 - oy0)
    rise = math.tan(math.radians(pitch)) * span / 2
    cx, cy, inset = (ox0 + ox1) / 2, (oy0 + oy1) / 2, span / 2
    if (ox1 - ox0) >= (oy1 - oy0):
        r0, r1 = (ox0 + inset, cy, z + rise), (ox1 - inset, cy, z + rise)
    else:
        r0, r1 = (cx, oy0 + inset, z + rise), (cx, oy1 - inset, z + rise)
    e = [(ox0, oy0, z), (ox1, oy0, z), (ox1, oy1, z), (ox0, oy1, z)]
    pts = e + [r0, r1]
    faces = [[0, 1, 4], [1, 5, 4], [1, 2, 5], [2, 3, 5], [3, 0, 4], [3, 4, 5]]
    return poly(pts, faces), z + rise


def gable_roof(x0, y0, x1, y1, z, pitch, oh):
    ox0, oy0, ox1, oy1 = x0 - oh, y0 - oh, x1 + oh, y1 + oh
    rise = math.tan(math.radians(pitch)) * (ox1 - ox0) / 2
    cx = (ox0 + ox1) / 2
    pts = [(ox0, oy0, z), (ox1, oy0, z), (ox1, oy1, z), (ox0, oy1, z),
           (cx, oy0, z + rise), (cx, oy1, z + rise)]
    faces = [[0, 1, 4], [3, 2, 5], [1, 2, 5], [1, 5, 4], [0, 4, 5], [0, 5, 3]]
    return poly(pts, faces), z + rise


# ----------------------------------------------------------------------------
# scene element collector
# ----------------------------------------------------------------------------
class Scene:
    def __init__(self):
        self.elems = []  # (mesh, material, map_plane, plane_tiles, color_override)

    def add(self, mesh, material, map_plane=False, plane_tiles=1.0, color=None):
        self.elems.append((mesh, material, map_plane, plane_tiles, color))


def build_scene(spec):
    lot = spec["lot_details"]
    bs = spec["building_specifications"]
    sb = spec["setbacks_m"]
    ext = spec.get("exterior", {})
    roof = spec.get("roof", {})
    facades = spec.get("facades", {})
    site = spec.get("site", {})

    W, D = lot["lot_frontage_m"], lot["lot_depth_m"]
    height = bs["building_height_m"]
    storeys = int(bs["number_of_storeys"])
    coverage = bs["lot_coverage_percent"] / 100.0
    lot_area = lot["lot_area_sqm"]

    x_west, x_east = sb["side_yard_west"], W - sb["side_yard_east"]
    y_front, y_rear_limit = sb["front_yard"], D - sb["rear_yard"]
    env_w = x_east - x_west
    foot_depth = min(coverage * lot_area / env_w, y_rear_limit - y_front)
    x0, x1 = x_west, x_east
    y0, y1 = y_front, y_front + foot_depth

    fnd = ext.get("foundation_height_m", 0.0)
    wall_mat = ext.get("wall_material", "brick")
    accent_mat = ext.get("accent_material", "stucco")

    s = Scene()

    # ----- ground: full grass lot (dirt only as a thin bed under building) -----
    s.add(quad((0, 0, 0), (W, 0, 0), (W, D, 0), (0, D, 0), W / 2.5, D / 2.5), "grass")
    s.add(quad((x0 - 0.3, y0 - 0.3, 0.01), (x1 + 0.3, y0 - 0.3, 0.01),
              (x1 + 0.3, y1 + 0.3, 0.01), (x0 - 0.3, y1 + 0.3, 0.01),
              (x1 - x0) / 2, (y1 - y0) / 2), "dirt")

    # driveway
    dv = site.get("driveway", {})
    if dv.get("present"):
        dw = dv.get("width_m", 3.0)
        dx0 = x0 if dv.get("side") == "west" else x1 - dw
        s.add(quad((dx0, 0, 0.02), (dx0 + dw, 0, 0.02), (dx0 + dw, y_front, 0.02),
                  (dx0, y_front, 0.02), dw / 2, y_front / 2), "concrete")

    # walkway
    wk = site.get("walkway", {})
    if wk.get("present"):
        ww = wk.get("width_m", 1.2)
        door = facades.get("front", {}).get("door", {})
        wcx = x0 + door.get("position_frac", 0.5) * (x1 - x0)
        s.add(quad((wcx - ww / 2, 0, 0.02), (wcx + ww / 2, 0, 0.02),
                  (wcx + ww / 2, y_front, 0.02), (wcx - ww / 2, y_front, 0.02),
                  1, y_front / 1.0), "paver")

    # fence
    fc = site.get("fence", {})
    if fc.get("present"):
        fh, t = fc.get("height_m", 1.8), 0.06
        for side in fc.get("sides", []):
            if side == "east":
                [s.add(m, "wood") for m in box(W - t, 0, 0, W, D, fh, tile=1.0)]
            elif side == "west":
                [s.add(m, "wood") for m in box(0, 0, 0, t, D, fh, tile=1.0)]
            elif side == "rear":
                [s.add(m, "wood") for m in box(0, D - t, 0, W, D, fh, tile=1.0)]

    # trees
    for tr in site.get("trees", []):
        add_tree(s, tr["x_m"], tr["y_m"], tr.get("height_m", 5.0),
                 tr.get("canopy_r_m", 1.6))

    # ----- foundation (proud stone band) -----
    base_z = fnd
    if fnd > 0:
        e = 0.08
        [s.add(m, "stone") for m in box(x0 - e, y0 - e, 0, x1 + e, y1 + e, fnd, tile=1.5)]

    # ----- massing (main + optional L wing) -----
    massing = spec.get("massing", {})
    blocks = [(x0, y0, x1, y1, height)]
    if massing.get("footprint_shape") == "L":
        wing = massing["wing"]
        ww = (x1 - x0) * wing.get("width_frac", 0.45)
        wd = (y1 - y0) * wing.get("depth_frac", 0.5)
        wh = wing.get("height_m", height)
        main_depth = (y1 - y0) - wd
        blocks = [(x0, y0, x1, y0 + main_depth, height)]
        if wing.get("side") == "east":
            blocks.append((x1 - ww, y0 + main_depth, x1, y1, wh))
        else:
            blocks.append((x0, y0 + main_depth, x0 + ww, y1, wh))

    for bi, (bx0, by0, bx1, by1, bh) in enumerate(blocks):
        mat = wall_mat if bi == 0 else accent_mat
        [s.add(m, mat) for m in box(bx0, by0, base_z, bx1, by1, bh, tile=1.5)]

    mbx0, mby0, mbx1, mby1, mbh = blocks[0]

    # ----- corner boards (white trim columns at the building corners) -----
    cb = 0.13
    for cxn in (mbx0, mbx1):
        for cyn in (mby0, mby1):
            sx = cb if cxn == mbx0 else -cb
            sy = cb if cyn == mby0 else -cb
            [s.add(m, "trim") for m in box(min(cxn, cxn + sx), min(cyn, cyn + sy),
                                           base_z, max(cxn, cxn + sx),
                                           max(cyn, cyn + sy), mbh, tile=1.0)]

    # ----- facade openings (windows / doors) -----
    def storey_z(level, sill):
        sh = (height - base_z) / storeys
        return base_z + (level - 1) * sh + sill

    # anchor openings to the MAIN BLOCK walls (not the full footprint),
    # otherwise rear/side windows float where the L-wing carves out the void.
    extent = {"front": (mbx0, mbx1), "rear": (mbx0, mbx1),
              "west": (mby0, mby1), "east": (mby0, mby1)}

    for face, fdata in facades.items():
        lo, hi = extent[face]
        for win in fdata.get("windows", []):
            cx = lo + win["position_frac"] * (hi - lo)
            zb = storey_z(win["storey"], win.get("sill_m", 1.0))
            add_window(s, face, mbx0, mby0, mbx1, mby1, cx, zb,
                       win["width_m"], win["height_m"])
        door = fdata.get("door")
        if door:
            cx = lo + door["position_frac"] * (hi - lo)
            add_door(s, face, mbx0, mby0, mbx1, mby1, cx, base_z,
                     door["width_m"], door["height_m"])

    # ----- porch -----
    porch = facades.get("front", {}).get("porch", {})
    if porch.get("present"):
        pd = porch.get("depth_m", 1.8)
        pw = (x1 - x0) * porch.get("width_frac", 0.55)
        ph = porch.get("height_m", 2.6)
        pcx = (x0 + x1) / 2
        px0, px1, py0, py1 = pcx - pw/2, pcx + pw/2, y0 - pd, y0
        [s.add(m, "wood") for m in box(px0, py0, base_z, px1, py1, base_z + 0.15, tile=1.0)]
        [s.add(m, "stucco") for m in box(px0, py0 - 0.1, ph, px1, py1, ph + 0.15, tile=1.5)]
        for ci in range(porch.get("columns", 2)):
            cxp = px0 + (ci + 0.5) * pw / porch.get("columns", 2)
            col = pv.Cylinder(center=(cxp, py0 + 0.15, (base_z + ph)/2),
                             direction=(0, 0, 1), radius=0.1, height=ph - base_z, resolution=16)
            s.add(col, "stucco", map_plane=True, plane_tiles=2.0)

    # ----- balcony -----
    bal = facades.get("rear", {}).get("balcony", {})
    if bal.get("present"):
        sh = (height - base_z) / storeys
        bz = base_z + (bal.get("storey", 2) - 1) * sh
        bw = (x1 - x0) * bal.get("width_frac", 0.4)
        bcx = x0 + bal.get("position_frac", 0.5) * (x1 - x0)
        bd = bal.get("depth_m", 1.5)
        ry = mby1  # attach to the main-block rear wall
        [s.add(m, "wood") for m in box(bcx - bw/2, ry, bz, bcx + bw/2, ry + bd, bz + 0.12, tile=1.0)]
        [s.add(m, "metal") for m in box(bcx - bw/2, ry + bd - 0.05, bz + 0.12,
                                        bcx + bw/2, ry + bd, bz + 1.0, tile=1.0, cap_top=False)]

    # ----- roof -----
    rtype = roof.get("type", "hip")
    pitch = roof.get("pitch_deg", 30)
    oh = roof.get("overhang_m", 0.4)
    if rtype == "hip":
        rmesh, ridge = hip_roof(mbx0, mby0, mbx1, mby1, mbh, pitch, oh)
    elif rtype == "gable":
        rmesh, ridge = gable_roof(mbx0, mby0, mbx1, mby1, mbh, pitch, oh)
    else:
        rmesh, ridge = poly(
            [(mbx0-oh, mby0-oh, mbh), (mbx1+oh, mby0-oh, mbh),
             (mbx1+oh, mby1+oh, mbh), (mbx0-oh, mby1+oh, mbh)],
            [[0, 1, 2, 3]]), mbh + 0.3
    s.add(rmesh, "shingle", map_plane=True, plane_tiles=(mbx1 - mbx0) / 1.4)

    for (bx0, by0, bx1, by1, bh) in blocks[1:]:
        flat = poly([(bx0, by0, bh), (bx1, by0, bh), (bx1, by1, bh), (bx0, by1, bh)],
                    [[0, 1, 2, 3]])
        s.add(flat, "shingle", map_plane=True, plane_tiles=(bx1 - bx0) / 1.4)

    # fascia / eave band (white trim under the roof overhang)
    fb = 0.2
    [s.add(m, "trim") for m in box(mbx0 - oh * 0.6, mby0 - oh * 0.6, mbh - fb,
                                   mbx1 + oh * 0.6, mby1 + oh * 0.6, mbh,
                                   tile=1.0, cap_top=False)]

    # chimney
    ch = roof.get("chimney", {})
    if ch.get("present"):
        cw = ch.get("width_m", 0.9)
        ctop = ridge + ch.get("height_above_ridge_m", 1.2)
        cxp = (mbx0 + cw) if ch.get("side") == "west" else (mbx1 - cw - 0.3)
        cyp = (mby0 + mby1) / 2
        [s.add(m, "brick") for m in box(cxp, cyp - cw/2, mbh, cxp + cw, cyp + cw/2, ctop, tile=1.0)]

    # dormers
    for dm in roof.get("dormers", []):
        if dm.get("face") != "front":
            continue
        dw, dh = dm.get("width_m", 1.6), dm.get("height_m", 1.3)
        dcx = mbx0 + dm.get("position_frac", 0.5) * (mbx1 - mbx0)
        dz = mbh + 0.2
        d_front = mby0 - oh + 0.1
        [s.add(m, "stucco") for m in box(dcx - dw/2, d_front, dz,
                                         dcx + dw/2, mby0 + 0.6, dz + dh, tile=1.0)]
        add_window(s, "front", mbx0, d_front, mbx1, mby1, dcx, dz + 0.2,
                   dw * 0.62, dh * 0.6, sill=False)

    return s, dict(W=W, D=D, ridge=ridge)


# ============================================================================
# TOWER / HIGH-RISE path  (podium + setback tower + penthouse, curtain wall)
# ============================================================================
def storey_levels(spec):
    """level -> (z_bottom, z_top) from the storeys[] heights."""
    z, out = 0.0, {}
    for st in spec.get("storeys", []):
        h = st["height_m"]
        out[st["level"]] = (z, z + h)
        z += h
    return out


def vzone_color(spec):
    """storey level -> (vision glass color, spandrel color)."""
    out = {}
    for vz in spec.get("vertical_zones", []):
        g = vz.get("wall_color", "#bcd6e8")
        sp = vz.get("spandrel_color", "#2a3a4a")
        for lv in vz.get("storeys", []):
            out[lv] = (g, sp)
    return out


def curtain_wall(s, bx0, by0, bx1, by1, levels, zmap, bay, zcol, bay_spandrel_h=1.0):
    """Glaze the 4 faces of an axis-aligned block: vision glass + spandrel bands
    + mullion grid. `levels` = storey numbers covering this block."""
    if not levels:
        return
    z0 = zmap[levels[0]][0]
    z1 = zmap[levels[-1]][1]
    eps, mt = 0.05, 0.05  # outward offset, mullion half-thickness
    faces = [
        ("y", by0, -1, "x", bx0, bx1),  # front
        ("y", by1, +1, "x", bx0, bx1),  # rear
        ("x", bx0, -1, "y", by0, by1),  # west
        ("x", bx1, +1, "y", by0, by1),  # east
    ]
    for axis, val, sgn, vax, a0, a1 in faces:
        gc, sc = zcol.get(levels[len(levels) // 2], ("#bcd6e8", "#2a3a4a"))
        off = val + sgn * eps

        def P(a, z):  # point on this wall plane
            return (a, off, z) if axis == "y" else (off, a, z)

        # vision glass sheet
        s.add(quad(P(a0, z0), P(a1, z0), P(a1, z1), P(a0, z1)), "glasscw", color=gc)
        # spandrel band + horizontal mullion at every floor line
        for lv in levels:
            fz0, fz1 = zmap[lv]
            zc = gc if lv not in zcol else zcol[lv][0]
            sc = zcol.get(lv, (gc, sc))[1]
            # spandrel (opaque) at slab
            s.add(quad(P(a0, fz0), P(a1, fz0), P(a1, fz0 + bay_spandrel_h),
                       P(a0, fz0 + bay_spandrel_h)), "spandrel", color=sc)
            # horizontal mullion
            if axis == "y":
                [s.add(m, "mullion") for m in box(a0, val - mt, fz0 - mt, a1, val + mt, fz0 + mt)]
            else:
                [s.add(m, "mullion") for m in box(val - mt, a0, fz0 - mt, val + mt, a1, fz0 + mt)]
        # vertical mullions every bay
        a = a0
        while a <= a1 + 0.01:
            if axis == "y":
                [s.add(m, "mullion") for m in box(a - mt, val - mt, z0, a + mt, val + mt, z1)]
            else:
                [s.add(m, "mullion") for m in box(val - mt, a - mt, z0, val + mt, a + mt, z1)]
            a += bay


def add_balcony_band(s, face, wall_x0, wall_y0, wall_x1, wall_y1, levels, zmap,
                     positions, bw, depth, alternating=False):
    """Cantilevered balcony slabs + glass railing on a tower face."""
    for i, lv in enumerate(levels):
        fz0, _ = zmap[lv]
        for j, pf in enumerate(positions):
            if alternating and (i + j) % 2:
                continue
            if face == "front":
                cx = wall_x0 + pf * (wall_x1 - wall_x0)
                bx0, bx1 = cx - bw / 2, cx + bw / 2
                y0, y1 = wall_y0 - depth, wall_y0
            elif face == "rear":
                cx = wall_x0 + pf * (wall_x1 - wall_x0)
                bx0, bx1 = cx - bw / 2, cx + bw / 2
                y0, y1 = wall_y1, wall_y1 + depth
            else:
                continue
            [s.add(m, "panel") for m in box(bx0, y0, fz0, bx1, y1, fz0 + 0.18, tile=1.0)]
            # glass railing (3 sides)
            rh = 1.05
            s.add(box(bx0, y0, fz0 + 0.18, bx1, y0 + 0.04, fz0 + rh, cap_top=False)[0]
                  if face == "front" else
                  box(bx0, y1 - 0.04, fz0 + 0.18, bx1, y1, fz0 + rh, cap_top=False)[0],
                  "glasscw")


def build_tower_scene(spec):
    lot = spec["lot_details"]
    sb = spec["setbacks_m"]
    fg = spec.get("facade_grid", {})
    facades = spec.get("facades", {})
    roof = spec.get("roof", {})
    site = spec.get("site", {})

    W, D = lot["lot_frontage_m"], lot["lot_depth_m"]
    zmap = storey_levels(spec)
    zcol = vzone_color(spec)

    # podium footprint from setbacks
    px0, px1 = sb["side_yard_west"], W - sb["side_yard_east"]
    py0, py1 = sb["front_yard"], D - sb["rear_yard"]
    podium_levels = [st["level"] for st in spec["storeys"] if st.get("zone") == "podium"]
    podium_top = zmap[podium_levels[-1]][1] if podium_levels else 13.5

    # tower footprint = podium inset by storey-4 stepbacks
    tx0 = px0 + sb.get("tower_stepback_side_west_at_storey_4", 3)
    tx1 = px1 - sb.get("tower_stepback_side_east_at_storey_4", 3)
    ty0 = py0 + sb.get("tower_stepback_front_at_storey_4", 5)
    ty1 = py1 - sb.get("tower_stepback_rear_at_storey_4", 5)

    s = Scene()

    # ----- ground -----
    grass = site.get("landscaping", {}).get("grass_color", "#7fb069")
    s.add(quad((0, 0, 0), (W, 0, 0), (W, D, 0), (0, D, 0), W / 2.5, D / 2.5), "grass",
          color=grass)
    dv = site.get("driveway", {})
    if dv.get("present"):
        dw = dv.get("width_m", 6.0)
        dx0 = 0 if dv.get("side") == "west" else W - dw
        s.add(quad((dx0, 0, 0.02), (dx0 + dw, 0, 0.02), (dx0 + dw, py0, 0.02),
                  (dx0, py0, 0.02), 2, 2), "granite", color=dv.get("color", "#4a4a4a"))
    for tr in site.get("trees", []):
        add_tree(s, tr["x_m"], tr["y_m"], tr.get("height_m", 8.0), tr.get("canopy_r_m", 2.5))

    # ----- podium (granite) -----
    pcol = next((vz.get("wall_color", "#3a3a3a") for vz in spec.get("vertical_zones", [])
                 if vz["id"] == "podium"), "#3a3a3a")
    [s.add(m, "granite", color=pcol) for m in box(px0, py0, 0, px1, py1, podium_top, tile=1.0)]

    # podium storefront glazing (level-1 front)
    front = facades.get("front", {})
    l1z0, l1z1 = zmap.get(1, (0, 5.5))
    for op in front.get("podium_retail_openings", []):
        cx = px0 + op["position_frac"] * (px1 - px0)
        w, h = op["width_m"], min(op["height_m"], podium_top - 0.3)
        gc = "#c0a060" if op.get("type") == "lobby_entrance" else "#1a2a3a"
        s.add(quad((cx - w/2, py0 - 0.04, 0.2), (cx + w/2, py0 - 0.04, 0.2),
                   (cx + w/2, py0 - 0.04, 0.2 + h), (cx - w/2, py0 - 0.04, 0.2 + h)),
              "glasscw", color=gc)
    # lobby canopy
    lob = front.get("lobby_entrance", {})
    if lob:
        cx = px0 + lob.get("position_frac", 0.5) * (px1 - px0)
        cw = lob.get("width_m", 5.0)
        cd = lob.get("canopy_depth_m", 2.0)
        [s.add(m, "gold") for m in box(cx - cw/2, py0 - cd, 5.2, cx + cw/2, py0, 5.4, tile=1.0)]

    # green roof on podium top
    if roof.get("green_roof_present"):
        s.add(quad((px0, py0, podium_top + 0.05), (px1, py0, podium_top + 0.05),
                   (px1, py1, podium_top + 0.05), (px0, py1, podium_top + 0.05),
                   (px1 - px0) / 2, (py1 - py0) / 2), "grass", color="#6fa05a")

    # ----- tower: lower (to upper stepback) + upper stepback block -----
    upper_levels = [st["level"] for st in spec["storeys"] if st.get("zone") == "tower_top"]
    tower_levels = [st["level"] for st in spec["storeys"]
                    if str(st.get("zone", "")).startswith("tower") and st["level"] not in upper_levels]
    bay = fg.get("tower_bay_width_m", 3.2)

    if tower_levels:
        lz1 = zmap[tower_levels[-1]][1]
        [s.add(m, "granite", color="#9fb4c4") for m in
         box(tx0, ty0, podium_top, tx1, ty1, lz1, tile=1.0)]   # structural backdrop
        curtain_wall(s, tx0, ty0, tx1, ty1, tower_levels, zmap, bay, zcol)

    uy0, uy1 = ty0, ty1  # upper-tower plane defaults to lower if no stepback
    if upper_levels:
        uy0 = ty0 + sb.get("upper_stepback_front_at_storey_12", 2.5)
        uy1 = ty1 - sb.get("upper_stepback_rear_at_storey_12", 2.5)
        uz0 = zmap[upper_levels[0]][0]
        uz1 = zmap[upper_levels[-1]][1]
        [s.add(m, "granite", color="#9fb4c4") for m in
         box(tx0, uy0, uz0, tx1, uy1, uz1, tile=1.0)]
        curtain_wall(s, tx0, uy0, tx1, uy1, upper_levels, zmap, bay, zcol)
        ty0u, ty1u = uy0, uy1  # rooflevel footprint for penthouse/equipment
    else:
        uz1, ty0u, ty1u = lz1, ty0, ty1

    # ----- balconies (attach to each storey's actual wall plane) -----
    def balconies(fdata, face):
        if not fdata:
            return
        levels = [l for l in fdata.get("storeys", []) if l in zmap]
        low = [l for l in levels if l not in upper_levels]
        up = [l for l in levels if l in upper_levels]
        kw = dict(positions=fdata.get("positions_frac", [0.2, 0.5, 0.8]),
                  bw=fdata.get("width_m", 2.4), depth=fdata.get("depth_m", 1.5),
                  alternating=fdata.get("pattern") == "alternating")
        add_balcony_band(s, face, tx0, ty0, tx1, ty1, low, zmap, **kw)   # lower plane
        add_balcony_band(s, face, tx0, uy0, tx1, uy1, up, zmap, **kw)    # stepped-back plane

    balconies(front.get("tower_balconies", {}), "front")
    balconies(facades.get("rear", {}).get("tower_balconies", {}), "rear")

    # ----- parapet around top -----
    par = roof.get("parapet", {})
    ph = par.get("height_m", 1.2)
    pc = par.get("color", "#2a3a4a")
    [s.add(m, "panel", color=pc) for m in box(tx0, ty0u, uz1, tx1, ty1u, uz1 + ph,
                                              tile=1.0, cap_top=False)]

    # ----- mechanical penthouse -----
    mp = roof.get("mechanical_penthouse", {})
    if mp.get("present"):
        mw, md, mh = mp["width_m"], mp["depth_m"], mp["height_m"]
        mcx, mcy = (tx0 + tx1) / 2, (ty0u + ty1u) / 2
        mx0, my0 = mcx - mw / 2, mcy - md / 2
        [s.add(m, "panel", color=mp.get("color", "#3a4a5a"))
         for m in box(mx0, my0, uz1, mx0 + mw, my0 + md, uz1 + mh, tile=1.0)]
        # rooftop equipment beside penthouse
        ex = mx0 - 2.5
        for eq in roof.get("rooftop_equipment", []):
            for n in range(min(eq.get("count", 1), 3)):
                w = eq.get("width_m", eq.get("diameter_m", 1.0))
                h = eq.get("height_m", 1.5)
                ey = my0 + n * 3.0
                if "stack" in eq.get("type", ""):
                    s.add(pv.Cylinder(center=(ex, ey, uz1 + h/2), direction=(0, 0, 1),
                                      radius=w/2, height=h, resolution=12), "mullion")
                else:
                    [s.add(m, "panel", color="#54636f")
                     for m in box(ex - w/2, ey - w/2, uz1, ex + w/2, ey + w/2, uz1 + h, tile=1.0)]

    return s, dict(W=W, D=D, ridge=uz1 + (mp.get("height_m", 0) if mp.get("present") else 0) + 2)


def is_tower(spec):
    m = spec.get("massing", {})
    return ("podium" in m) or ("vertical_zones" in spec) or \
        bool(spec.get("building_specifications", {}).get("podium_storeys"))


def build_any(spec):
    return build_tower_scene(spec) if is_tower(spec) else build_scene(spec)


# ----------------------------------------------------------------------------
# measurement axes (Frontage / Depth / Height) — Plotly-style labeled frame.
# Built from real geometry (grid lines + extruded 3D text) so it survives the
# vtk.js HTML export, which drops CubeAxesActor titles on export.
# ----------------------------------------------------------------------------
_AX_GRID = "#cfd8e3"   # faint ground grid
_AX_LINE = "#5b6b7d"   # axis baselines
_AX_TXT  = "#33414f"   # tick + title text


def _nice_step(span, target=6):
    raw = span / target
    if raw <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw:
            return m * mag
    return 10 * mag


def _axis_ticks(span):
    s = _nice_step(span)
    n = int(math.floor(span / s + 1e-9))
    return [round(i * s, 4) for i in range(n + 1)]


def _axis_label(text, size, anchor, kind):
    """Extruded 3D text sized to glyph height `size`, anchored at `anchor`.
    kind: 'x' flat read +x | 'y' flat read +y | 'z' upright read +x |
          'zt' vertical title read +z (camera-facing, not mirrored)."""
    m = pv.Text3D(text, depth=0.01)
    b = m.bounds
    m.scale([size / (b.y_max - b.y_min)] * 3, inplace=True)
    b = m.bounds
    m.translate([-(b.x_min + b.x_max) / 2, -b.y_min, 0], inplace=True)  # center x, baseline y
    if kind == "y":
        m.rotate_z(90, inplace=True)
    elif kind == "z":
        m.rotate_x(90, inplace=True)
    elif kind == "zt":
        m.rotate_x(90, inplace=True)
        m.rotate_y(-90, inplace=True)
    m.translate(anchor, inplace=True)
    return m


def add_measure_frame(pl, dims):
    """Add a Plotly-style Frontage/Depth/Height labeled frame to the plotter."""
    W, D = dims["W"], dims["D"]
    H = float(math.ceil(dims["ridge"]))
    xs, ys, zs = _axis_ticks(W), _axis_ticks(D), _axis_ticks(H)

    lines = [pv.Line((x, 0, 0), (x, D, 0)) for x in xs]
    lines += [pv.Line((0, y, 0), (W, y, 0)) for y in ys]
    grid = lines[0].merge(lines[1:]) if len(lines) > 1 else lines[0]
    pl.add_mesh(grid, color=_AX_GRID, line_width=1, lighting=False)

    base = pv.Line((0, 0, 0), (W, 0, 0)).merge(
        [pv.Line((W, 0, 0), (W, D, 0)), pv.Line((0, 0, 0), (0, 0, H))])
    pl.add_mesh(base, color=_AX_LINE, line_width=2, lighting=False)

    sz = max(W, D, H) * 0.035
    fmt = lambda v: "%g" % v
    for x in xs:
        pl.add_mesh(_axis_label(fmt(x), sz, (x, -sz * 1.4, 0), "x"), color=_AX_TXT, ambient=1.0, diffuse=0.0, specular=0.0)
    for y in ys:
        pl.add_mesh(_axis_label(fmt(y), sz, (W + sz * 1.4, y, 0), "y"), color=_AX_TXT, ambient=1.0, diffuse=0.0, specular=0.0)
    for z in zs:
        pl.add_mesh(_axis_label(fmt(z), sz, (-sz * 2.5, 0, z), "z"), color=_AX_TXT, ambient=1.0, diffuse=0.0, specular=0.0)
    t = sz * 1.5
    pl.add_mesh(_axis_label("Frontage (m)", t, (W / 2, -sz * 5, 0), "x"), color=_AX_TXT, ambient=1.0, diffuse=0.0, specular=0.0)
    pl.add_mesh(_axis_label("Depth (m)", t, (W + sz * 5, D / 2, 0), "y"), color=_AX_TXT, ambient=1.0, diffuse=0.0, specular=0.0)
    pl.add_mesh(_axis_label("Height (m)", t * 0.95, (-sz * 4.0, 0, H * 0.5), "zt"),
                color=_AX_TXT, ambient=1.0, diffuse=0.0, specular=0.0)


# ----------------------------------------------------------------------------
# render
# ----------------------------------------------------------------------------
def render(spec, mode, out_html, screenshot=None, glb_out=None):
    scene, dims = build_any(spec)
    pv.global_theme.allow_empty_mesh = True
    lk = "none" if mode == "hq" else "light_kit"
    pl = pv.Plotter(off_screen=True, window_size=(1500, 1000), lighting=lk)

    for mesh, matname, map_plane, plane_tiles, cov in scene.elems:
        if mode == "blueprint":
            _add_blueprint_mesh(pl, mesh, matname)
            continue
        if matname == "_canopy":
            pl.add_mesh(mesh, color=cov or "#4f8b3b", ambient=0.4, diffuse=0.85,
                        specular=0.08, smooth_shading=True)
            continue
        if matname == "_shadow":
            if mode == "hq":  # real shadows handle this; skip fake disc
                continue
            pl.add_mesh(mesh, color="#2c3a22", opacity=0.18, lighting=False)
            continue
        mat = MATERIALS[matname]
        opacity = mat.get("opacity", 1.0)
        color = cov or mat["color"]
        glossy = matname in ("glass", "metal", "glasscw", "gold")
        if mode == "hq" and mat["tex"]:
            # poly()-based meshes (local_box in add_window/add_door) carry no
            # texcoords; project a plane so the texture has UVs to sample.
            if map_plane or mesh.active_texture_coordinates is None:
                mesh = mesh.texture_map_to_plane(inplace=False)
                if mesh.active_texture_coordinates is not None:
                    mesh.active_texture_coordinates = (
                        mesh.active_texture_coordinates * plane_tiles)
            # textured + diffuse lighting (PBR w/o an IBL env renders flat/gray)
            pl.add_mesh(mesh, texture=get_texture(mat["tex"]),
                        ambient=0.3, diffuse=0.95, specular=0.1,
                        specular_power=18, opacity=opacity, smooth_shading=False)
        elif mode == "hq" and glossy:  # glass / metal: reflective
            pl.add_mesh(mesh, color=color, ambient=0.22, diffuse=0.55,
                        specular=0.95, specular_power=60,
                        opacity=opacity, smooth_shading=True)
        elif mode == "hq":  # matte solid (trim / stone / granite / spandrel)
            pl.add_mesh(mesh, color=color, ambient=0.3, diffuse=0.92,
                        specular=0.12, specular_power=20, opacity=opacity,
                        smooth_shading=False)
        else:  # normal flat mode
            pl.add_mesh(mesh, color=color, opacity=opacity,
                        smooth_shading=False, show_edges=False)

    if mode == "blueprint":
        pl.set_background(_BP_BG)
        W, D, R = dims["W"], dims["D"], dims["ridge"]
        # ground grid — technical-drawing feel
        grid = pv.Plane(center=(W / 2, D / 2, 0), direction=(0, 0, 1),
                        i_size=W * 2, j_size=D * 2, i_resolution=20, j_resolution=20)
        pl.add_mesh(grid, color="#003a50", opacity=0.25,
                    style="wireframe", line_width=0.5, lighting=False)
        # flat ambient-only light (no directional shadows — pure topology read)
        amb = pv.Light(light_type="headlight", intensity=1.0)
        pl.add_light(amb)
        pl.enable_anti_aliasing("ssaa")
        reach = max(W, D, R)
        pl.camera_position = [
            (W / 2 + reach * 1.1, -reach * 0.9, R * 0.82),
            (W / 2, D / 2, R * 0.38),
            (0, 0, 1),
        ]
    elif mode == "hq":
        pl.set_background("#bcdcf2", top="#eef7ff")
        # warm sun (key) + cool sky fill, so shadows have direction
        W, D, R = dims["W"], dims["D"], dims["ridge"]
        sun = pv.Light(position=(W * 1.2, -D * 0.5, R * 4), focal_point=(W/2, D/2, R*0.3),
                       color="#fff4e0", intensity=1.15)
        sun.positional = False
        fill = pv.Light(position=(-W * 0.6, D * 1.4, R * 2.5), focal_point=(W/2, D/2, R*0.3),
                        color="#d6e6ff", intensity=0.6)
        fill.positional = False
        amb = pv.Light(light_type="headlight", intensity=0.25)
        pl.add_light(sun)
        pl.add_light(fill)
        pl.add_light(amb)
        pl.enable_anti_aliasing("ssaa")
        try:
            pl.enable_shadows()
        except Exception:
            pass
    else:
        pl.set_background("#f4f7fb", top="#ffffff")

    if mode in ("hq", "normal"):
        add_measure_frame(pl, dims)
    pl.add_axes()
    if mode != "blueprint":
        W, D, R = dims["W"], dims["D"], dims["ridge"]
        reach = max(W, D, R)
        pl.camera_position = [
            (W / 2 + reach * 1.05, -reach * 0.85, R * 0.75),   # eye
            (W / 2, D / 2, R * 0.42),                           # focal
            (0, 0, 1),
        ]
    if screenshot:
        pl.screenshot(screenshot)
        print(f"Wrote {screenshot}")
    if glb_out:
        # best-effort web-friendly model export; non-fatal if VTK's exporter
        # chokes on the scene (the HTML below is the primary deliverable).
        try:
            pl.export_gltf(glb_out)
            print(f"Wrote {glb_out}")
        except Exception as e:  # noqa: BLE001
            print(f"glTF export skipped: {e}")
    pl.export_html(out_html)
    pl.close()
    if mode in ("hq", "normal"):
        inject_controls(out_html)
    print(f"Wrote {out_html}  (mode={mode})")


_BLUEPRINT_PANEL = r"""
<style>
#bp-panel{position:fixed;top:16px;right:16px;z-index:9999;background:rgba(4,12,24,0.88);
border:1px solid #1a3a5a;border-radius:10px;padding:14px 16px;font-family:monospace;
backdrop-filter:blur(10px);user-select:none;box-shadow:0 4px 28px rgba(0,0,0,.7);min-width:160px;}
#bp-panel .lbl{color:#80eeff;font-size:10px;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;}
#bp-btn{width:100%;padding:8px 14px;cursor:pointer;border:1px solid #00d4ff55;
background:#061828;color:#00d4ff;border-radius:6px;font-family:monospace;font-size:12px;
letter-spacing:1px;transition:all .2s;}
#bp-btn:hover{background:#0a2a40;}
#bp-themes{display:none;margin-top:10px;}
#bp-themes .lbl{margin-bottom:6px;}
.bp-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;}
.bp-t{padding:6px 4px;border-radius:5px;cursor:pointer;font-family:monospace;font-size:11px;
border:1px solid;text-align:center;transition:all .15s;letter-spacing:.5px;}
.bp-t:hover{filter:brightness(1.3);}
.bp-t.active{font-weight:bold;filter:brightness(1.5);}
#bp-t-cyan    {background:#020d1a;color:#00d4ff;border-color:#00d4ff44;}
#bp-t-amber   {background:#1a1000;color:#ffb800;border-color:#ffb80044;}
#bp-t-matrix  {background:#001a00;color:#00ff41;border-color:#00ff4144;}
#bp-t-infrared{background:#1a0400;color:#ff6422;border-color:#ff642244;}
</style>
<div id="bp-panel">
  <div class="lbl">Render Mode</div>
  <button id="bp-btn" onclick="bpToggle()">&#x25C8; Blueprint</button>
  <div id="bp-themes">
    <div class="lbl" style="margin-top:8px;">Color Theme</div>
    <div class="bp-grid">
      <div id="bp-t-cyan"     class="bp-t active" onclick="bpTheme('cyan')">Cyan</div>
      <div id="bp-t-amber"    class="bp-t"        onclick="bpTheme('amber')">Amber</div>
      <div id="bp-t-matrix"   class="bp-t"        onclick="bpTheme('matrix')">Matrix</div>
      <div id="bp-t-infrared" class="bp-t"        onclick="bpTheme('infrared')">Infrared</div>
    </div>
  </div>
</div>
<script>
(function(){
  var _r=null,_rw=null,_orig=null,_bg=null,_on=false,_theme='cyan';
  var THEMES={
    cyan:     {fill:[0.02,0.05,0.10],edge:[0.00,0.83,1.00],bg:[0.012,0.051,0.102]},
    amber:    {fill:[0.10,0.06,0.01],edge:[1.00,0.72,0.00],bg:[0.060,0.040,0.005]},
    matrix:   {fill:[0.01,0.07,0.01],edge:[0.00,1.00,0.25],bg:[0.005,0.040,0.005]},
    infrared: {fill:[0.10,0.02,0.01],edge:[1.00,0.39,0.13],bg:[0.060,0.010,0.005]}
  };
  function actorsOf(r){
    // prefer real actors; fall back to view props (synchronizer may add props
    // before getActors() enumerates them).
    var a=r.getActors?r.getActors():null;
    if(a&&a.length)return a;
    var vp=r.getViewProps?r.getViewProps():null;
    return vp||[];
  }
  function findRen(){
    // vtk.js bundle does: global.renderWindow = n  where global = window.global.
    // The export has TWO renderers: the building scene (hundreds of actors) and
    // the orientation-axes widget (1 actor). renderers[0] is not reliably the
    // building one, so scan all and pick the renderer with the most actors.
    var rw=(window.global||{}).renderWindow;
    if(!rw)return null;
    var rs=rw.getRenderers?rw.getRenderers():(rw.getRenderersByReference?rw.getRenderersByReference():[]);
    if(!rs||!rs.length)return null;
    var best=null,bestN=0;
    for(var i=0;i<rs.length;i++){
      var n=actorsOf(rs[i]).length;
      if(n>bestN){bestN=n;best=rs[i];}
    }
    if(best){_rw=rw;return best;}
    return null;
  }
  function poll(){
    var r=findRen();
    if(!r){setTimeout(poll,200);return;}
    _r=r;
  }
  function clr3(arr){return arr?[arr[0],arr[1],arr[2]]:[1,1,1];}
  function capture(){
    if(_orig)return;
    var bg=_r.getBackgroundByReference?_r.getBackgroundByReference():_r.getBackground?_r.getBackground():[0.74,0.86,0.95];
    _bg=clr3(bg);
    _orig=actorsOf(_r).map(function(actor){
      var p=actor.getProperty();
      // save ambient + diffuse color arrays (PyVista sets these, not t.color)
      var dc=p.getDiffuseColorByReference?clr3(p.getDiffuseColorByReference()):clr3(p.getDiffuseColor?p.getDiffuseColor():null);
      var ac=p.getAmbientColorByReference?clr3(p.getAmbientColorByReference()):clr3(p.getAmbientColor?p.getAmbientColor():null);
      return{actor:actor,dc:dc,ac:ac,
        opacity:p.getOpacity?p.getOpacity():1,
        rep:p.getRepresentation?p.getRepresentation():2,
        edgeVis:p.getEdgeVisibility?p.getEdgeVisibility():false,
        edgeOp:p.getEdgeOpacity?p.getEdgeOpacity():1};
    });
  }
  function applyTheme(name){
    capture();
    var t=THEMES[name]||THEMES.cyan;
    actorsOf(_r).forEach(function(actor){
      var p=actor.getProperty();
      p.setRepresentation(2);
      if(p.setDiffuseColor)p.setDiffuseColor(t.fill[0],t.fill[1],t.fill[2]);
      if(p.setAmbientColor)p.setAmbientColor(t.fill[0],t.fill[1],t.fill[2]);
      if(p.setOpacity)p.setOpacity(0.15);
      if(p.setEdgeVisibility)p.setEdgeVisibility(true);
      if(p.setEdgeColor)p.setEdgeColor(t.edge[0],t.edge[1],t.edge[2]);
      if(p.setEdgeOpacity)p.setEdgeOpacity(1.0);
    });
    if(_r.setBackground)_r.setBackground(t.bg[0],t.bg[1],t.bg[2]);
    _rw.render();
  }
  function restoreAll(){
    if(!_orig)return;
    _orig.forEach(function(s){
      var p=s.actor.getProperty();
      if(p.setDiffuseColor)p.setDiffuseColor(s.dc[0],s.dc[1],s.dc[2]);
      if(p.setAmbientColor)p.setAmbientColor(s.ac[0],s.ac[1],s.ac[2]);
      if(p.setOpacity)p.setOpacity(s.opacity);
      if(p.setRepresentation)p.setRepresentation(s.rep);
      if(p.setEdgeVisibility)p.setEdgeVisibility(s.edgeVis);
      if(p.setEdgeOpacity)p.setEdgeOpacity(s.edgeOp);
    });
    if(_bg&&_r.setBackground)_r.setBackground(_bg[0],_bg[1],_bg[2]);
    _rw.render();
  }
  function setActiveBtn(name){
    ['cyan','amber','matrix','infrared'].forEach(function(t){
      var el=document.getElementById('bp-t-'+t);
      if(el)el.classList.toggle('active',t===name);
    });
  }
  window.bpToggle=function(){
    if(!_r)_r=findRen();   // lazy resolve in case poll has not landed yet
    if(!_r){alert('Scene still loading — try again in a moment.');return;}
    _on=!_on;
    var btn=document.getElementById('bp-btn');
    var panel=document.getElementById('bp-themes');
    if(_on){
      applyTheme(_theme);
      btn.textContent='◈ Normal';
      btn.style.color='#ffffff';
      btn.style.borderColor='#ffffff44';
      panel.style.display='block';
    }else{
      restoreAll();
      btn.textContent='◈ Blueprint';
      btn.style.color='#00d4ff';
      btn.style.borderColor='#00d4ff55';
      panel.style.display='none';
    }
  };
  window.bpTheme=function(name){
    if(!_r||!_on)return;
    _theme=name;
    applyTheme(name);
    setActiveBtn(name);
  };
  setTimeout(poll,600);
})();
</script>
"""


def inject_controls(html_path):
    """Inject floating Blueprint toggle + color theme switcher into vtk.js HTML."""
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</body>", _BLUEPRINT_PANEL + "\n</body>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", nargs="?", default=os.path.join(SPECS_DIR, "discription_building.json"))
    ap.add_argument("--mode", choices=["normal", "hq", "both", "blueprint"], default="hq")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--png", action="store_true", help="also write PNG screenshot")
    args = ap.parse_args()

    if not os.path.isdir(TEX_DIR) or not os.listdir(TEX_DIR):
        tx.generate_all()

    with open(args.spec) as f:
        spec = json.load(f)

    out_dir = OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    modes = ["normal", "hq"] if args.mode == "both" else [args.mode]
    for m in modes:
        out = args.out or os.path.join(out_dir, f"building_{m}.html")
        if args.mode == "both":
            out = os.path.join(out_dir, f"building_{m}.html")
        shot = out.replace(".html", ".png") if args.png else None
        render(spec, m, out, shot)


if __name__ == "__main__":
    main()
