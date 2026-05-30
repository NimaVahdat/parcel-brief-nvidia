"""generate() — the contract function.

Real path: ZoningEnvelope -> LLM building spec -> validation/repair -> 3D render
-> MassingOutput, via ``massing_generator.builder``. Used automatically when an
Anthropic API key is configured.

Mock path: deterministic, envelope-respecting options via ``massing_fit`` — real lot
area from the footprint, GFA <= max_fsi * lot_area, height <= the cap, and a unit mix
consistent with the GFA. Used when no API key is present (so the end-to-end brief
pipeline and tests still run offline), when ``MASSING_USE_MOCK=1``, or if the real
engine raises for any reason. On this path the 3D visuals (three_d_uri,
facade_renders) stay mock placeholders; only the numbers are real.
"""

from __future__ import annotations

import logging
import os

from massing_generator.massing_fit import fit_massing, lot_area_m2
from massing_generator.schemas import Massing, MassingOutput, ZoningEnvelope

log = logging.getLogger(__name__)

# (variant tag, design directive) — drives the real LLM engine. The directive
# nudges the design intent; hard caps from the envelope always hold.
_DIRECTIVES: list[tuple[str, str]] = [
    ("market", "Maximize leasable area within the caps with a standard market-rate unit mix."),
    (
        "affordable",
        "Include at least 12 affordable residential units and a family-friendly mix "
        "(more 2-bedroom and 3-bedroom units).",
    ),
    (
        "conservative",
        "Lower-rise, context-sensitive massing comfortably below the height cap, "
        "with smaller floorplates.",
    ),
]

# (label, GFA fraction of the FSI cap, affordable share) — drives the mock path,
# fed through ``fit_massing`` so the numbers respect the legal envelope.
_MOCK_OPTIONS: list[tuple[str, float, float]] = [
    ("max-density", 1.00, 0.0),
    ("affordable", 0.95, 0.15),
    ("conservative", 0.70, 0.08),
]


def _engine_available() -> bool:
    """Real engine runs only when explicitly configured with an API key."""
    if os.getenv("MASSING_USE_MOCK") == "1":
        return False
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def generate(
    envelope: ZoningEnvelope,
    *,
    num_options: int | None = None,
    use_mock: bool | None = None,
    render: bool = True,
) -> MassingOutput:
    """Generate viable 3D building massings for a zoning envelope.

    Runs the real LLM-spec + 3D-render engine when an Anthropic API key is
    configured, otherwise returns deterministic, envelope-respecting mock options.
    Pass ``use_mock=True`` to force the mock. ``num_options`` (or the
    ``MASSING_NUM_OPTIONS`` env var) controls how many real design variants are
    produced — each is a separate LLM call, so the default is 1.
    """
    if use_mock is None:
        use_mock = not _engine_available()
    if use_mock:
        return _mock_output(envelope)
    try:
        return _real_output(envelope, num_options=num_options, render=render)
    except (Exception, SystemExit) as e:  # llm_client raises SystemExit if the SDK is absent
        log.warning("massing engine failed (%s); returning mock output", e)
        return _mock_output(envelope)


def _real_output(
    envelope: ZoningEnvelope, *, num_options: int | None, render: bool
) -> MassingOutput:
    from massing_generator.builder import pipeline

    if num_options is None:
        num_options = int(os.getenv("MASSING_NUM_OPTIONS", "1"))
    num_options = max(1, min(num_options, len(_DIRECTIVES)))
    render_mode = os.getenv("MASSING_RENDER_MODE", "hq")

    options: list[Massing] = []
    for variant, note in _DIRECTIVES[:num_options]:
        spec = pipeline.build_spec(envelope, design_note=note)
        if spec is None:
            log.warning("variant %s: no valid spec produced; skipping", variant)
            continue
        if render:
            artifacts = pipeline.render_spec(
                spec, f"{envelope.parcel_id}-{variant}", mode=render_mode
            )
        else:
            artifacts = pipeline.RenderArtifacts(
                three_d_uri=f"spec://{envelope.parcel_id}-{variant}"
            )
        options.append(pipeline.spec_to_massing(spec, envelope, variant, artifacts))

    if not options:
        raise RuntimeError("engine produced no valid massing options")
    return MassingOutput(options=options)


def _mock_output(envelope: ZoningEnvelope) -> MassingOutput:
    """Deterministic, envelope-respecting options — no LLM, no render.

    Numbers (GFA, height, unit mix, retail, affordable) fit the legal envelope and
    are internally consistent via ``massing_fit``; the 3D URIs stay mock placeholders
    until the real renderer fills them in.
    """
    lot_area = lot_area_m2(envelope.footprint_polygon) or 1000.0
    has_retail = "retail" in (envelope.permitted_uses or [])

    from massing_generator import massing3d  # plotly only; lazy import

    options: list[Massing] = []
    for label, frac, affordable_share in _MOCK_OPTIONS:
        fit = fit_massing(
            max_height_m=envelope.max_height_m,
            max_fsi=envelope.max_fsi,
            lot_area=lot_area,
            has_retail=has_retail,
            gfa_fraction=frac,
            affordable_share=affordable_share,
        )
        m = Massing(
            massing_id=f"{envelope.parcel_id}-{label}",
            height_m=fit["height_m"],
            total_gfa_m2=fit["total_gfa_m2"],
            unit_mix=fit["unit_mix"],
            retail_sqft=fit["retail_sqft"],
            affordable_units=fit["affordable_units"],
            three_d_uri=f"mock://massing/{envelope.parcel_id}-{label}.glb",
            facade_renders=[],
        )
        # clean deterministic 3D render (instant, no LLM); falls back to the mock URI
        uri = massing3d.render_to_uri(envelope, m, f"{envelope.parcel_id}-{label}")
        if uri:
            m.three_d_uri = uri
        options.append(m)
    return MassingOutput(options=options)
