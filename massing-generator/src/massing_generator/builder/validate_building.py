"""
Validate a building-spec JSON for STRUCTURAL / geometric consistency.

Not a JSON-syntax linter — it checks that the described building is buildable:
fits the lot, setbacks leave a positive envelope, storey heights add up,
coverage/FSI are consistent, tower stepbacks/penthouse fit, openings land on
real walls, balconies reference real storeys, etc.

Schema-aware: auto-detects house vs mixed-use tower.

Usage (from repo root):
    python src/validate_building.py [specs/spec.json]
    python src/validate_building.py specs/spec.json --strict   # warnings -> failure

Exit code: 0 = clean (or warnings), 1 = errors found, 2 = strict + warnings.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SPEC = os.path.join(HERE, "specs", "discription_building.json")

ERROR, WARN, OK, INFO = "ERROR", "WARN", "OK", "INFO"
TOL = 0.03  # 3% relative tolerance


# ----------------------------------------------------------------------------
class Report:
    def __init__(self):
        self.items = []

    def add(self, level, where, msg):
        self.items.append((level, where, msg))

    def error(self, where, msg): self.add(ERROR, where, msg)
    def warn(self, where, msg):  self.add(WARN, where, msg)
    def ok(self, where, msg):    self.add(OK, where, msg)
    def info(self, where, msg):  self.add(INFO, where, msg)

    def count(self, level):
        return sum(1 for l, _, _ in self.items if l == level)

    def print(self):
        color = {ERROR: "\033[91m", WARN: "\033[93m", OK: "\033[92m", INFO: "\033[96m"}
        sym = {ERROR: "✗", WARN: "▲", OK: "✓", INFO: "•"}
        reset = "\033[0m"
        # errors & warnings first, then ok/info
        order = {ERROR: 0, WARN: 1, INFO: 2, OK: 3}
        for level, where, msg in sorted(self.items, key=lambda i: order[i[0]]):
            c = color[level]
            print(f"  {c}{sym[level]} {level:5}{reset} [{where}] {msg}")


def num(d, *path, default=None):
    """Safely fetch a nested numeric value."""
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    try:
        return float(cur)
    except (TypeError, ValueError):
        return default


def close(a, b, rel=TOL, ab=0.5):
    if a is None or b is None:
        return False
    return abs(a - b) <= max(rel * max(abs(a), abs(b)), ab)


def is_tower(spec):
    m = spec.get("massing", {})
    return ("podium" in m) or ("vertical_zones" in spec) or \
        bool(spec.get("building_specifications", {}).get("podium_storeys"))


# ----------------------------------------------------------------------------
# shared checks
# ----------------------------------------------------------------------------
def check_required(spec, r):
    for key in ("lot_details", "building_specifications", "setbacks_m"):
        if key not in spec:
            r.error("schema", f"missing required section '{key}'")


def check_lot(spec, r):
    W = num(spec, "lot_details", "lot_frontage_m")
    D = num(spec, "lot_details", "lot_depth_m")
    A = num(spec, "lot_details", "lot_area_sqm")
    for nm, v in (("lot_frontage_m", W), ("lot_depth_m", D), ("lot_area_sqm", A)):
        if v is None:
            r.error("lot", f"missing {nm}")
        elif v <= 0:
            r.error("lot", f"{nm} must be > 0 (got {v})")
    if W and D and A:
        if close(W * D, A, rel=0.05):
            r.ok("lot", f"area consistent with frontage×depth ({W}×{D}≈{A} m²)")
        else:
            r.warn("lot", f"area {A} m² != frontage×depth {W*D:.1f} m² "
                          f"(irregular lot? off by {abs(A-W*D):.0f} m²)")
    return W, D, A


def envelope(spec, W, D, r):
    """Buildable envelope from setbacks; returns (x0,x1,y0,y1,w,d) or None."""
    sb = spec.get("setbacks_m", {})
    fy, ry = num(sb, "front_yard", default=0), num(sb, "rear_yard", default=0)
    se, sw = num(sb, "side_yard_east", default=0), num(sb, "side_yard_west", default=0)
    if None in (fy, ry, se, sw) or W is None or D is None:
        r.warn("setbacks", "incomplete setbacks; skipping envelope check")
        return None
    ew, ed = W - se - sw, D - fy - ry
    if ew <= 0:
        r.error("setbacks", f"side setbacks ({sw}+{se}) >= frontage {W} → no width left")
    if ed <= 0:
        r.error("setbacks", f"front+rear setbacks ({fy}+{ry}) >= depth {D} → no depth left")
    if ew > 0 and ed > 0:
        r.ok("setbacks", f"buildable envelope {ew:.1f}×{ed:.1f} m ({ew*ed:.0f} m²)")
        return sw, W - se, fy, D - ry, ew, ed
    return None


def check_height_sum(spec, r):
    bh = num(spec, "building_specifications", "building_height_m")
    storeys = spec.get("storeys", [])
    if not storeys:
        return
    total = sum(num(st, "height_m", default=0) for st in storeys)
    # mechanical/penthouse may push above stated building height; compare loosely
    if bh is None:
        r.warn("height", "no building_height_m to compare storey sum against")
    elif close(total, bh, rel=0.06):
        r.ok("height", f"storey heights sum to {total:.1f} m ≈ building_height {bh}")
    elif total > bh:
        r.warn("height", f"storey heights sum {total:.1f} m > building_height {bh} m "
                         f"(penthouse/mech above stated height?)")
    else:
        r.warn("height", f"storey heights sum {total:.1f} m < building_height {bh} m")


def check_coverage_fsi(spec, env, A, r):
    cov = num(spec, "building_specifications", "lot_coverage_percent")
    gfa = num(spec, "building_specifications", "gross_floor_area_sqm")
    fsi = num(spec, "building_specifications", "floor_space_index")
    if cov is not None and A:
        foot = cov / 100.0 * A
        if env and foot > env[4] * env[5] + 0.5:
            r.error("coverage", f"footprint {foot:.0f} m² ({cov}%) exceeds buildable "
                                f"envelope {env[4]*env[5]:.0f} m² — cannot fit within setbacks")
        else:
            r.ok("coverage", f"footprint {foot:.0f} m² ({cov}%) fits envelope")
    if gfa and A and fsi is not None:
        if close(gfa / A, fsi, rel=0.05):
            r.ok("FSI", f"GFA/lot {gfa/A:.2f} ≈ floor_space_index {fsi}")
        else:
            r.warn("FSI", f"GFA/lot = {gfa/A:.2f} but floor_space_index = {fsi}")


# ----------------------------------------------------------------------------
# house checks
# ----------------------------------------------------------------------------
def check_house(spec, env, r):
    n = int(num(spec, "building_specifications", "number_of_storeys", default=0) or 0)
    bh = num(spec, "building_specifications", "building_height_m")
    sh = (bh / n) if (bh and n) else None
    ew = env[4] if env else None

    for face, fd in spec.get("facades", {}).items():
        if not isinstance(fd, dict):
            continue
        for win in fd.get("windows", []):
            st = win.get("storey")
            if st and n and st > n:
                r.error("windows", f"{face} window on storey {st} but building has {n}")
            # window must fit wall height of its storey
            if sh:
                top = num(win, "sill_m", default=1.0) + num(win, "height_m", default=0)
                if top > sh + 0.05:
                    r.warn("windows", f"{face} storey {st} window top {top:.1f} m "
                                      f"> storey height {sh:.1f} m (clips ceiling)")
            # window must fit wall width
            if ew:
                pf = num(win, "position_frac", default=0.5)
                half = num(win, "width_m", default=0) / 2
                if pf * ew - half < -0.05 or pf * ew + half > ew + 0.05:
                    r.warn("windows", f"{face} window (pos {pf}, w {win.get('width_m')}) "
                                      f"extends past the {ew:.1f} m wall")
        door = fd.get("door")
        if door and sh:
            dh = num(door, "height_m", default=0)
            if dh > sh:
                r.warn("doors", f"{face} door height {dh} m exceeds storey {sh:.1f} m")

    mass = spec.get("massing", {})
    if mass.get("footprint_shape") == "L":
        wing = mass.get("wing", {})
        for k in ("width_frac", "depth_frac"):
            v = num(wing, k)
            if v is not None and not (0 < v < 1):
                r.error("massing", f"L-wing {k}={v} must be between 0 and 1")
    if not spec.get("facades"):
        r.info("facades", "no facade openings defined (blank walls)")


# ----------------------------------------------------------------------------
# tower checks
# ----------------------------------------------------------------------------
def check_tower(spec, env, r):
    storeys = spec.get("storeys", [])
    levels = [int(num(st, "level", default=-1)) for st in storeys]
    zmap_levels = set(levels)

    # storey levels contiguous from 1
    if levels:
        expected = list(range(min(levels), max(levels) + 1))
        if sorted(levels) != expected:
            r.error("storeys", f"levels not contiguous: {sorted(levels)}")
        elif len(set(levels)) != len(levels):
            r.error("storeys", "duplicate storey levels")
        else:
            r.ok("storeys", f"{len(levels)} contiguous storeys ({min(levels)}–{max(levels)})")

    # vertical_zones cover every storey exactly once
    zones = spec.get("vertical_zones", [])
    zone_ids = {z.get("id") for z in zones}
    covered = {}
    for z in zones:
        for lv in z.get("storeys", []):
            covered[lv] = covered.get(lv, 0) + 1
    for lv in zmap_levels:
        st = next((s for s in storeys if num(s, "level") == lv), {})
        zname = st.get("zone")
        # mechanical penthouse may live outside vertical_zones
        if covered.get(lv, 0) == 0 and zname in zone_ids:
            r.error("zones", f"storey {lv} not listed in any vertical_zone")
        if covered.get(lv, 0) > 1:
            r.error("zones", f"storey {lv} appears in multiple vertical_zones")
        if zname and zname not in zone_ids and "mech" not in str(zname):
            r.warn("zones", f"storey {lv} zone '{zname}' has no matching vertical_zone id")
    if zones and not any(l for l in covered if covered[l] > 1):
        r.ok("zones", f"{len(zones)} vertical zones, no storey overlaps")

    # massing nesting: tower must fit inside podium after stepbacks
    sb = spec.get("setbacks_m", {})
    if env:
        x0, x1, y0, y1, ew, ed = env
        tx0 = x0 + num(sb, "tower_stepback_side_west_at_storey_4", default=0)
        tx1 = x1 - num(sb, "tower_stepback_side_east_at_storey_4", default=0)
        ty0 = y0 + num(sb, "tower_stepback_front_at_storey_4", default=0)
        ty1 = y1 - num(sb, "tower_stepback_rear_at_storey_4", default=0)
        if tx1 - tx0 <= 0 or ty1 - ty0 <= 0:
            r.error("massing", "tower stepbacks consume the entire podium footprint")
        else:
            r.ok("massing", f"tower floorplate {tx1-tx0:.1f}×{ty1-ty0:.1f} m fits podium")
            # upper stepback must leave a positive plate
            uy0 = ty0 + num(sb, "upper_stepback_front_at_storey_12", default=0)
            uy1 = ty1 - num(sb, "upper_stepback_rear_at_storey_12", default=0)
            if uy1 - uy0 <= 0:
                r.error("massing", "upper stepback consumes the whole tower depth")
            elif uy1 - uy0 < ty1 - ty0:
                r.ok("massing", f"upper crown plate {uy1-uy0:.1f} m deep")
            # mechanical penthouse footprint must sit on the crown
            mp = spec.get("roof", {}).get("mechanical_penthouse", {})
            if mp.get("present"):
                if num(mp, "width_m", default=0) > tx1 - tx0 + 0.1 or \
                   num(mp, "depth_m", default=0) > uy1 - uy0 + 0.1:
                    r.warn("massing", "mechanical penthouse larger than the roof it sits on")

    # balconies / tower windows reference real storeys
    def check_storey_refs(node, label):
        for lv in node.get("storeys", []):
            if lv not in zmap_levels:
                r.error("facades", f"{label} references storey {lv} that doesn't exist")
    for face, fd in spec.get("facades", {}).items():
        if not isinstance(fd, dict):
            continue
        if "tower_balconies" in fd:
            check_storey_refs(fd["tower_balconies"], f"{face} tower_balconies")
        if "tower_windows" in fd:
            check_storey_refs(fd["tower_windows"], f"{face} tower_windows")

    # podium storey count vs declared
    pod = int(num(spec, "building_specifications", "podium_storeys", default=0) or 0)
    pod_actual = sum(1 for s in storeys if s.get("zone") == "podium")
    if pod and pod_actual and pod != pod_actual:
        r.warn("massing", f"podium_storeys={pod} but {pod_actual} storeys tagged podium")


# ----------------------------------------------------------------------------
def validate(spec):
    r = Report()
    check_required(spec, r)
    W, D, A = check_lot(spec, r)
    env = envelope(spec, W, D, r)
    check_height_sum(spec, r)
    check_coverage_fsi(spec, env, A, r)
    if is_tower(spec):
        r.info("schema", "detected MIXED-USE TOWER schema")
        check_tower(spec, env, r)
    else:
        r.info("schema", "detected HOUSE / low-rise schema")
        check_house(spec, env, r)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", nargs="?", default=DEFAULT_SPEC)
    ap.add_argument("--strict", action="store_true", help="treat warnings as failure")
    args = ap.parse_args()

    try:
        with open(args.spec) as f:
            spec = json.load(f)
    except json.JSONDecodeError as e:
        print(f"\033[91m✗ invalid JSON: {e}\033[0m")
        sys.exit(1)
    except FileNotFoundError:
        print(f"\033[91m✗ file not found: {args.spec}\033[0m")
        sys.exit(1)

    name = spec.get("project_name", args.spec)
    print(f"\nValidating: {name}\n" + "─" * 60)
    r = validate(spec)
    r.print()
    print("─" * 60)
    ne, nw = r.count(ERROR), r.count(WARN)
    verdict = (f"\033[91m{ne} error(s)\033[0m" if ne else "\033[92mno errors\033[0m")
    print(f"  {verdict}, \033[93m{nw} warning(s)\033[0m\n")

    if ne:
        sys.exit(1)
    if args.strict and nw:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
