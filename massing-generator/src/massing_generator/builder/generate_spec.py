"""
Turn a high-level zoning brief (raw/raw_discription.json) into a full building
spec (specs/*.json) that the renderers consume.

Pipeline:
  1. PREPROCESS (deterministic, no LLM) — the parts that must be exact:
       geo footprint_polygon -> metric lot dims + area
       compass setbacks       -> front/rear/side (south = street/front)
       max_fsi                -> GFA ceiling;  max_height -> storey ceiling
       permitted_uses, parking_minimum carried through as hard caps
  2. DESIGN (LLM) — invent everything the brief does NOT constrain: storeys,
       materials, facades, massing, unit mix, ... WITHIN the caps from step 1.
  3. VALIDATE (validate_building.py) — geometric/structural compliance gate.
       On errors, feed the report back to the LLM and regenerate (repair loop).

Usage (from repo root):
    python src/generate_spec.py [raw/raw_discription.json] -o specs/generated.json
    python src/generate_spec.py --provider anthropic --max-repairs 3
    python src/generate_spec.py --dry-run        # print constraints only, no LLM
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re

try:  # package import
    from . import validate_building as vb
    from .llm_client import get_client
    from .paths import OUTPUT_DIR, SPECS_DIR
except ImportError:  # running as a standalone script from this directory
    import validate_building as vb
    from llm_client import get_client
    from paths import OUTPUT_DIR, SPECS_DIR

DEFAULT_RAW = os.path.join(SPECS_DIR, "raw_discription.json")
DEFAULT_OUT = os.path.join(OUTPUT_DIR, "generated.json")
EXAMPLE_SPEC = os.path.join(SPECS_DIR, "discription_building.json")

TYP_FLOOR_M = 3.4  # assumed avg floor-to-floor for the storey-count estimate


# ---------------------------------------------------------------------------
# 1. PREPROCESS — deterministic geometry + constraint extraction
# ---------------------------------------------------------------------------
def _shoelace(pts: list[tuple[float, float]]) -> float:
    """Polygon area (m²) from a list of (x, y); closed or open ring."""
    if pts and pts[0] == pts[-1]:
        pts = pts[:-1]
    s = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


def geo_to_metric(poly: list[list[float]]) -> tuple[float, float, float]:
    """[[lon,lat],...] -> (frontage_m E-W, depth_m N-S, area_m²).

    Equirectangular projection about the parcel's mean latitude. Good to <1%
    at parcel scale, which is all we need for lot dims.
    """
    lons = [p[0] for p in poly]
    lats = [p[1] for p in poly]
    lat0 = sum(lats) / len(lats)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))
    pts = [((lon - min(lons)) * m_per_deg_lon, (lat - min(lats)) * m_per_deg_lat)
           for lon, lat in poly]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    frontage = max(xs) - min(xs)
    depth = max(ys) - min(ys)
    return round(frontage, 2), round(depth, 2), round(_shoelace(pts), 1)


def preprocess(raw: dict) -> dict:
    """Brief -> hard constraints + derived lot geometry the LLM must respect."""
    frontage, depth, area = geo_to_metric(raw["footprint_polygon"])
    sb = raw.get("setbacks", {})
    # south faces the street -> front; map compass -> renderer's frame.
    setbacks_m = {
        "front_yard": float(sb.get("south", 0.0)),
        "rear_yard": float(sb.get("north", 0.0)),
        "side_yard_east": float(sb.get("east", 0.0)),
        "side_yard_west": float(sb.get("west", 0.0)),
    }
    max_h = float(raw["max_height_m"])
    max_fsi = float(raw["max_fsi"])
    uses = raw.get("permitted_uses", [])
    mixed_use = "retail" in uses and "residential" in uses
    tall = max_h >= 20.0
    return {
        "parcel_id": raw.get("parcel_id"),
        "lot": {
            "lot_frontage_m": frontage,
            "lot_depth_m": depth,
            "lot_area_sqm": area,
            "orientation_deg": 0,
        },
        "setbacks_m": setbacks_m,
        "buildable_envelope_m": {
            "width_m": round(frontage - setbacks_m["side_yard_east"]
                             - setbacks_m["side_yard_west"], 2),
            "depth_m": round(depth - setbacks_m["front_yard"]
                             - setbacks_m["rear_yard"], 2),
        },
        "caps": {
            "max_height_m": max_h,
            "max_fsi": max_fsi,
            "max_gross_floor_area_sqm": round(max_fsi * area, 1),
            "max_storeys_estimate": max(1, int(max_h // TYP_FLOOR_M)),
            "permitted_uses": uses,
            "parking_minimum": raw.get("parking_minimum", 0),
        },
        "schema_hint": "tower" if (tall or mixed_use) else "house",
    }


# ---------------------------------------------------------------------------
# 2. DESIGN — prompt assembly + LLM call
# ---------------------------------------------------------------------------
SCHEMA_GUIDE = """\
You are a senior architect + Toronto zoning examiner. You convert a zoning brief
into a COMPLETE, buildable building-spec JSON for a 3D renderer.

Two schemas exist; pick by the schema_hint and the brief:

HOUSE / low-rise: lot_details, building_specifications, setbacks_m, exterior,
roof, facades{front,rear,east,west each with windows[]/door}, massing
(footprint_shape rectangular|L), site.

MIXED-USE TOWER (use for tall and/or mixed residential+retail): adds
  storeys[]            per-floor {level,height_m,floor_to_floor_m,use,zone,stepback?}
  vertical_zones[]     {id,storeys[],use,facade_system,wall_material,colors,...}
                       zones must cover every storey exactly once
                       (mechanical_penthouse may sit outside vertical_zones)
  facade_grid          bay widths, mullion dims, glass tint, parapet height
  massing.podium / .tower / .mechanical_penthouse  (tower nests inside podium
                       after stepbacks; penthouse sits on the crown)
  setbacks_m.tower_stepback_*_at_storey_N
  facades per side: podium openings + tower_balconies/tower_windows {storeys[],...}
  roof (flat, parapet, mechanical_penthouse, rooftop_equipment[]),
  structural_system, vertical_circulation, underground_parking, lobby, site,
  sustainability, unit_mix.

Coordinate frame: x = frontage (E-W), y = depth (front=0 at south/street -> rear
at north), z = up. Front facade faces south. west = low x, east = high x.

HARD CONSTRAINTS (a spec that violates any is rejected):
  - lot_details.{lot_frontage_m,lot_depth_m,lot_area_sqm} = the provided values
  - setbacks_m front/rear/side = the provided values; footprint fits the
    buildable envelope (coverage * area <= envelope width*depth)
  - building_height_m <= caps.max_height_m
  - gross_floor_area_sqm / lot_area_sqm  ~= floor_space_index  and <= caps.max_fsi
  - every storey use is within caps.permitted_uses
  - underground_parking spaces >= caps.parking_minimum (0 => parking optional)
  - storey heights sum ~= building_height_m; storey levels contiguous from 1;
    vertical_zones cover each storey once; balconies/windows reference real storeys

Design freely (materials, colors, unit mix, facade rhythm, landscaping) but stay
inside the caps. Match the structure and key names of the provided EXAMPLE spec.

OUTPUT: a single JSON object only. No prose, no markdown fences.
"""


def _example_block() -> str:
    with open(EXAMPLE_SPEC) as f:
        spec = json.load(f)
    return json.dumps(spec, indent=2, sort_keys=True)


def build_system() -> list[dict]:
    """Stable, large prefix -> cached across the repair loop and across runs."""
    text = (
        SCHEMA_GUIDE
        + "\n\nEXAMPLE mixed-use tower spec (match this structure):\n"
        + _example_block()
    )
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def first_user_message(raw: dict, constraints: dict) -> str:
    return (
        "Zoning brief (raw):\n"
        + json.dumps(raw, indent=2)
        + "\n\nDerived constraints you MUST honor (metric, already computed):\n"
        + json.dumps(constraints, indent=2)
        + "\n\nGenerate the full building-spec JSON now. Output JSON only."
    )


def next_building_path(dirpath: str) -> str:
    """Next free specs/building_NN.json in `dirpath` (zero-padded, +1 over max)."""
    os.makedirs(dirpath, exist_ok=True)
    nums = [int(m.group(1))
            for f in glob.glob(os.path.join(dirpath, "building_*.json"))
            if (m := re.search(r"building_(\d+)\.json$", os.path.basename(f)))]
    return os.path.join(dirpath, f"building_{(max(nums) + 1) if nums else 0:02}.json")


def parse_json(text: str) -> dict:
    """Tolerate stray prose / markdown fences around the JSON object."""
    t = text.strip()
    if "```" in t:
        # take the content of the first fenced block
        seg = t.split("```", 2)
        t = seg[1] if len(seg) > 1 else t
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b == -1:
        raise ValueError("no JSON object found in model output")
    return json.loads(t[a : b + 1])


# ---------------------------------------------------------------------------
# 3. VALIDATE — reuse validate_building, format errors for the repair turn
# ---------------------------------------------------------------------------
def validation_report(spec: dict) -> tuple[int, str]:
    r = vb.validate(spec)
    n_err = r.count(vb.ERROR)
    lines = [f"[{lvl}] ({where}) {msg}"
             for lvl, where, msg in r.items if lvl in (vb.ERROR, vb.WARN)]
    return n_err, "\n".join(lines) if lines else "(no errors or warnings)"


# ---------------------------------------------------------------------------
# library entry point (used by massing_generator.builder.pipeline)
# ---------------------------------------------------------------------------
def run(raw: dict, *, provider: str = "anthropic", model: str | None = None,
        max_repairs: int = 3, design_note: str | None = None,
        verbose: bool = False) -> dict | None:
    """Brief dict -> validated building-spec dict.

    Runs the deterministic preprocess, one LLM design pass, then up to
    `max_repairs` validator-driven repair turns. Returns the best spec produced
    (may still carry warnings), or None if the model never emitted valid JSON.
    `design_note` nudges the design intent (e.g. "include affordable units")
    without relaxing the hard caps.
    """
    constraints = preprocess(raw)
    client = get_client(provider, model)
    system = build_system()
    user = first_user_message(raw, constraints)
    if design_note:
        user += "\n\nDESIGN DIRECTIVE (honour all hard caps above): " + design_note
    messages = [{"role": "user", "content": user}]

    spec = None
    for attempt in range(max_repairs + 1):
        if verbose:
            print(f"[{client.name}] generating (attempt {attempt + 1})...")
        text = client.generate(system, messages)
        try:
            spec = parse_json(text)
        except (ValueError, json.JSONDecodeError) as e:
            if verbose:
                print(f"  parse error: {e}")
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content":
                 f"That was not valid JSON ({e}). Return ONLY the JSON object."},
            ]
            continue

        n_err, report = validation_report(spec)
        if verbose:
            print(report)
        if n_err == 0:
            if verbose:
                print(f"✓ valid spec ({attempt + 1} attempt(s))")
            break
        if verbose:
            print(f"✗ {n_err} error(s) — feeding back for repair")
        messages += [
            {"role": "assistant", "content": json.dumps(spec)},
            {"role": "user", "content":
             "The spec has validation ERRORS:\n" + report
             + "\n\nFix every ERROR (keep the lot dims, setbacks, and caps "
               "unchanged) and return the full corrected JSON object only."},
        ]
    return spec


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", nargs="?", default=DEFAULT_RAW)
    ap.add_argument("-o", "--out", default=DEFAULT_OUT)
    ap.add_argument("--provider", default="anthropic", help="anthropic | custom")
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-repairs", type=int, default=3,
                    help="validator-driven regeneration attempts")
    ap.add_argument("--dry-run", action="store_true",
                    help="print derived constraints and exit (no LLM call)")
    ap.add_argument("--auto-name", action="store_true",
                    help="write to specs/building_NN.json (auto-incremented)")
    args = ap.parse_args()

    if args.auto_name and not args.dry_run:
        args.out = next_building_path(os.path.dirname(os.path.abspath(args.out)))

    with open(args.raw) as f:
        raw = json.load(f)
    constraints = preprocess(raw)

    print("Derived constraints")
    print("─" * 60)
    print(json.dumps(constraints, indent=2))
    print("─" * 60)
    if args.dry_run:
        path = next_building_path(os.path.dirname(os.path.abspath(args.out)))
        with open(path, "w") as f:
            json.dump(constraints, f, indent=2)
        print(f"wrote {path}")
        return

    spec = run(raw, provider=args.provider, model=args.model,
               max_repairs=args.max_repairs, verbose=True)
    if spec is None:
        print("\n⚠ model never produced valid JSON; nothing written")
        return

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"\nwrote {args.out}")
    print(f"render: python -m massing_generator.builder.render_pyvista {args.out} --mode hq")


if __name__ == "__main__":
    main()
