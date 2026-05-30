"""Smoke test."""

from massing_generator import generate
from massing_generator.schemas import MassingOutput, ZoningEnvelope


def test_generate_returns_massing_output() -> None:
    envelope = ZoningEnvelope(
        parcel_id="test",
        max_height_m=30.0,
        max_fsi=3.0,
        setbacks={"north": 3.0, "south": 0.0, "east": 1.5, "west": 1.5},
        permitted_uses=["residential"],
        footprint_polygon=[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)],
    )
    output = generate(envelope)
    assert isinstance(output, MassingOutput)
    assert len(output.options) >= 1
    assert all(m.three_d_uri for m in output.options)
