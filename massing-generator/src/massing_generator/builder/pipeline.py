"""Glue between the ZoningEnvelope contract and the building-spec engine.

Flow:  ZoningEnvelope -> raw brief -> LLM building spec (validated) -> 3D render
       -> Massing.

Kept deliberately light to import: the spec generator (`generate_spec`) only
needs the stdlib + a lazily-imported LLM client, and the renderers / texture
generator (numpy, plotly, pyvista, PIL) are imported lazily inside the render
helpers so `import massing_generator` never drags in heavy deps.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from massing_generator.schemas import Massing, ZoningEnvelope

from . import generate_spec
from .paths import OUTPUT_DIR, TEXTURES_DIR, ensure_dirs

log = logging.getLogger(__name__)

# Map building-spec unit_mix keys onto the contract's compact unit codes.
_UNIT_KEYMAP = {
    "studio": "studio",
    "bachelor": "studio",
    "junior_one_bedroom": "1br",
    "one_bedroom": "1br",
    "1_bedroom": "1br",
    "1br": "1br",
    "two_bedroom": "2br",
    "2_bedroom": "2br",
    "2br": "2br",
    "three_bedroom": "3br",
    "3_bedroom": "3br",
    "3br": "3br",
    "penthouse": "penthouse",
}
_M2_TO_SQFT = 10.7639


# ---------------------------------------------------------------------------
# ZoningEnvelope -> raw brief (the engine's `raw_discription.json` shape)
# ---------------------------------------------------------------------------
def envelope_to_raw(envelope: ZoningEnvelope) -> dict:
    """Contract envelope -> the brief dict the spec engine ingests."""
    return {
        "parcel_id": envelope.parcel_id,
        "max_height_m": float(envelope.max_height_m),
        "max_fsi": float(envelope.max_fsi),
        "setbacks": dict(envelope.setbacks),
        "permitted_uses": list(envelope.permitted_uses),
        "footprint_polygon": [list(pt) for pt in envelope.footprint_polygon],
        "parking_minimum": int(envelope.parking_minimum or 0),
    }


# ---------------------------------------------------------------------------
# building spec -> Massing fields
# ---------------------------------------------------------------------------
def _unit_mix(spec: dict) -> dict[str, int]:
    raw = spec.get("unit_mix") or {}
    out: dict[str, int] = {}
    for key, val in raw.items():
        if key in ("total_residential_units", "total_units"):
            continue
        count = val.get("count") if isinstance(val, dict) else val
        try:
            count = int(count)
        except (TypeError, ValueError):
            continue
        code = _UNIT_KEYMAP.get(key, key)
        out[code] = out.get(code, 0) + count
    if not out and not _is_tower(spec):
        out = {"dwelling": 1}
    return out


def _is_tower(spec: dict) -> bool:
    m = spec.get("massing", {})
    return (
        ("podium" in m)
        or ("vertical_zones" in spec)
        or bool(spec.get("building_specifications", {}).get("podium_storeys"))
    )


def _retail_sqft(spec: dict) -> float:
    bs = spec.get("building_specifications", {})
    lot = spec.get("lot_details", {})
    cov = bs.get("lot_coverage_percent")
    area = lot.get("lot_area_sqm")
    retail_levels = sum(
        1 for s in spec.get("storeys", []) if "retail" in str(s.get("use", "")).lower()
    )
    if cov and area and retail_levels:
        footprint = cov / 100.0 * area
        return round(footprint * retail_levels * _M2_TO_SQFT, 1)
    return 0.0


def _affordable_units(spec: dict) -> int:
    um = spec.get("unit_mix", {}) or {}
    for key in ("affordable", "affordable_units"):
        v = um.get(key)
        if isinstance(v, dict):
            v = v.get("count")
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    try:
        return int(spec.get("affordable_units"))
    except (TypeError, ValueError):
        return 0


@dataclass
class RenderArtifacts:
    three_d_uri: str
    facade_renders: list[str] = field(default_factory=list)
    spec_path: str | None = None


def spec_to_massing(
    spec: dict,
    envelope: ZoningEnvelope,
    variant: str,
    artifacts: RenderArtifacts,
) -> Massing:
    bs = spec.get("building_specifications", {})
    return Massing(
        massing_id=f"{envelope.parcel_id}-{variant}",
        height_m=float(bs.get("building_height_m", envelope.max_height_m)),
        total_gfa_m2=float(bs.get("gross_floor_area_sqm", 0.0)),
        unit_mix=_unit_mix(spec),
        retail_sqft=_retail_sqft(spec),
        affordable_units=_affordable_units(spec),
        three_d_uri=artifacts.three_d_uri,
        facade_renders=artifacts.facade_renders,
    )


# ---------------------------------------------------------------------------
# spec generation + rendering
# ---------------------------------------------------------------------------
def build_spec(
    envelope: ZoningEnvelope,
    *,
    design_note: str | None = None,
    provider: str = "anthropic",
    model: str | None = None,
    max_repairs: int = 2,
    verbose: bool = False,
) -> dict | None:
    """ZoningEnvelope -> validated building-spec dict (needs an LLM)."""
    raw = envelope_to_raw(envelope)
    return generate_spec.run(
        raw,
        provider=provider,
        model=model,
        max_repairs=max_repairs,
        design_note=design_note,
        verbose=verbose,
    )


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(text)).strip("-") or "massing"


def ensure_textures() -> None:
    """Generate the procedural PBR textures if they are not present yet."""
    TEXTURES_DIR.mkdir(parents=True, exist_ok=True)
    if any(TEXTURES_DIR.glob("*.png")):
        return
    from . import textures as tx  # heavy (numpy + PIL); imported lazily

    tx.generate_all()


def render_spec(spec: dict, basename: str, *, mode: str = "hq") -> RenderArtifacts:
    """Render a building spec to a 3D artifact.

    Prefers the textured PyVista renderer (interactive HTML + PNG + best-effort
    glTF). Falls back to the dependency-light Plotly renderer, and finally to
    just writing the spec JSON, so a result is always produced even on a
    headless box without VTK.
    """
    ensure_dirs()
    base = _slug(basename)
    spec_path = OUTPUT_DIR / f"{base}.json"
    spec_path.write_text(json.dumps(spec, indent=2))

    html_path = OUTPUT_DIR / f"{base}.html"
    png_path = OUTPUT_DIR / f"{base}.png"
    glb_path = OUTPUT_DIR / f"{base}.glb"

    if mode != "plotly":
        try:
            from . import render_pyvista  # heavy: pyvista/VTK

            ensure_textures()
            render_pyvista.render(
                spec, mode, str(html_path), screenshot=str(png_path), glb_out=str(glb_path)
            )
            three_d = str(glb_path) if glb_path.exists() else str(html_path)
            renders = [str(png_path)] if png_path.exists() else []
            return RenderArtifacts(three_d, renders, str(spec_path))
        except Exception as e:  # noqa: BLE001
            log.warning("PyVista render failed (%s); falling back to Plotly", e)

    try:
        from . import build_3d  # plotly only — works headless

        fig = build_3d.make_figure(spec)
        fig.write_html(str(html_path), include_plotlyjs="cdn", auto_open=False)
        return RenderArtifacts(str(html_path), [], str(spec_path))
    except Exception as e:  # noqa: BLE001
        log.warning("Plotly render failed (%s); returning spec only", e)

    return RenderArtifacts(str(spec_path), [], str(spec_path))
