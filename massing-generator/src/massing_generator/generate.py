"""generate() — the contract function.

Produces 2-3 massing options that fit the legal envelope with internally consistent
numbers (GFA, height, units, retail, affordable). The 3D visuals (three_d_uri,
facade_renders) remain mock placeholders here — the SDXL/ControlNet renderer
(controlnet.py) fills those in; it doesn't change these numbers.
"""

from __future__ import annotations

from massing_generator.massing_fit import fit_massing, lot_area_m2
from massing_generator.schemas import Massing, MassingOutput, ZoningEnvelope

# (label, GFA fraction of the FSI cap, affordable share)
_OPTIONS = [
    ("max-density", 1.00, 0.0),
    ("affordable", 0.95, 0.15),
    ("conservative", 0.70, 0.08),
]


def generate(envelope: ZoningEnvelope) -> MassingOutput:
    """Generate viable building massings for a zoning envelope."""
    lot_area = lot_area_m2(envelope.footprint_polygon) or 1000.0
    has_retail = "retail" in (envelope.permitted_uses or [])

    options = []
    for label, frac, affordable_share in _OPTIONS:
        fit = fit_massing(
            max_height_m=envelope.max_height_m,
            max_fsi=envelope.max_fsi,
            lot_area=lot_area,
            has_retail=has_retail,
            gfa_fraction=frac,
            affordable_share=affordable_share,
        )
        options.append(
            Massing(
                massing_id=f"{envelope.parcel_id}-{label}",
                height_m=fit["height_m"],
                total_gfa_m2=fit["total_gfa_m2"],
                unit_mix=fit["unit_mix"],
                retail_sqft=fit["retail_sqft"],
                affordable_units=fit["affordable_units"],
                three_d_uri=f"mock://massing/{envelope.parcel_id}-{label}.glb",
                facade_renders=[f"mock://render/{envelope.parcel_id}-{label}-n.png"],
            )
        )
    return MassingOutput(options=options)
