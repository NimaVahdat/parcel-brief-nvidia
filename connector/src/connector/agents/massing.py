"""Massing agent — calls massing_generator, and evaluates user overrides if given.

Normally the auto-generated options drive the brief. When the user supplies project
overrides (height / units / affordable / retail), we build a "custom" massing that
respects the envelope caps and make it the evaluated option[0] — so the pro-forma,
approval, community and recommendation all reflect *the user's* building. The auto
options remain as alternatives in the design comparison.
"""

from massing_generator import generate as generate_massing
from massing_generator.schemas import ZoningEnvelope as MassingZoningEnvelope

from connector.agents.state import BriefState
from connector.schemas.brief import Massing, MassingOutput

_GFA_PER_UNIT = 85.0
_SQFT_PER_SQM = 10.7639
_MIX = {"studio": 0.15, "1br": 0.45, "2br": 0.30, "3br": 0.10}


def _split_units(n: int) -> dict[str, int]:
    n = max(0, int(n))
    mix = {k: int(n * r) for k, r in _MIX.items()}
    mix["1br"] += n - sum(mix.values())
    return {k: v for k, v in mix.items() if v > 0}


def _custom_massing(base: Massing, envelope, ov: dict) -> Massing:
    """Build the user's building from overrides, clamped to the legal envelope."""
    height = min(float(ov.get("height_m") or base.height_m), envelope.max_height_m)
    units = int(ov.get("total_units") or sum(base.unit_mix.values()) or 1)
    retail = float(ov["retail_sqft"]) if "retail_sqft" in ov else base.retail_sqft
    affordable = int(ov["affordable_units"]) if "affordable_units" in ov else base.affordable_units
    affordable = max(0, min(affordable, units))
    gfa = round(units * _GFA_PER_UNIT + retail / _SQFT_PER_SQM, 0)
    return Massing(
        massing_id=f"{envelope.parcel_id}-custom",
        height_m=round(height, 1),
        total_gfa_m2=gfa,
        unit_mix=_split_units(units),
        retail_sqft=round(retail, 0),
        affordable_units=affordable,
        three_d_uri=base.three_d_uri,
        facade_renders=base.facade_renders,
    )


def massing_agent(state: BriefState) -> BriefState:
    envelope = state["site_fundamentals"]
    massing_envelope = MassingZoningEnvelope.model_validate(envelope.model_dump())
    output = generate_massing(massing_envelope)
    options = [Massing.model_validate(m.model_dump()) for m in output.options]

    overrides = state.get("overrides") or {}
    if overrides and options:
        custom = _custom_massing(options[0], envelope, overrides)
        options = [custom, *options]  # evaluated option[0] = the user's building

    return {"design_options": MassingOutput(options=options)}
