"""generate() — the contract function.

Real path: ZoningEnvelope -> LLM building spec -> validation/repair -> 3D render
-> MassingOutput, via ``massing_generator.builder``. Used automatically when an
Anthropic API key is configured.

Mock path: deterministic placeholder options. Used when no API key is present
(so the end-to-end brief pipeline and tests still run offline), when
``MASSING_USE_MOCK=1``, or if the real engine raises for any reason.
"""

from __future__ import annotations

import logging
import os

from massing_generator.schemas import Massing, MassingOutput, ZoningEnvelope

log = logging.getLogger(__name__)

# (variant tag, design directive) — mirrors the three mock options below. The
# directive nudges the design intent; hard caps from the envelope always hold.
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
    configured, otherwise returns deterministic mock options. Pass
    ``use_mock=True`` to force the mock. ``num_options`` (or the
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
    """Deterministic placeholder options — no LLM, no render."""
    base_height = envelope.max_height_m
    base_gfa = envelope.max_fsi * 1500  # placeholder lot area

    options = [
        Massing(
            massing_id=f"{envelope.parcel_id}-tall",
            height_m=base_height,
            total_gfa_m2=base_gfa,
            unit_mix={"studio": 12, "1br": 30, "2br": 28, "3br": 14},
            retail_sqft=2400,
            affordable_units=0,
            three_d_uri=f"mock://massing/{envelope.parcel_id}-tall.glb",
            facade_renders=[f"mock://render/{envelope.parcel_id}-tall-n.png"],
        ),
        Massing(
            massing_id=f"{envelope.parcel_id}-affordable",
            height_m=base_height,
            total_gfa_m2=base_gfa,
            unit_mix={"studio": 16, "1br": 32, "2br": 24, "3br": 12},
            retail_sqft=2400,
            affordable_units=12,
            three_d_uri=f"mock://massing/{envelope.parcel_id}-affordable.glb",
            facade_renders=[f"mock://render/{envelope.parcel_id}-affordable-n.png"],
        ),
        Massing(
            massing_id=f"{envelope.parcel_id}-conservative",
            height_m=base_height * 0.75,
            total_gfa_m2=base_gfa * 0.75,
            unit_mix={"1br": 24, "2br": 20, "3br": 10},
            retail_sqft=1800,
            affordable_units=6,
            three_d_uri=f"mock://massing/{envelope.parcel_id}-conservative.glb",
            facade_renders=[f"mock://render/{envelope.parcel_id}-conservative-n.png"],
        ),
    ]
    return MassingOutput(options=options)
