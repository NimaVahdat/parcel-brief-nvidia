"""Smoke + mapping + offline-render tests (no LLM / no network)."""

import json
from pathlib import Path

import pytest
from massing_generator import generate
from massing_generator.builder import pipeline
from massing_generator.builder import validate_building as vb
from massing_generator.builder.paths import SPECS_DIR
from massing_generator.schemas import MassingOutput, ZoningEnvelope

ENVELOPE = ZoningEnvelope(
    parcel_id="test",
    max_height_m=30.0,
    max_fsi=3.0,
    setbacks={"north": 3.0, "south": 0.0, "east": 1.5, "west": 1.5},
    permitted_uses=["residential"],
    footprint_polygon=[(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)],
)

TOWER_SPEC = json.loads((SPECS_DIR / "discription_building.json").read_text())


def test_generate_returns_massing_output() -> None:
    output = generate(ENVELOPE, use_mock=True)
    assert isinstance(output, MassingOutput)
    assert len(output.options) >= 1
    assert all(m.three_d_uri for m in output.options)
    assert all(isinstance(v, int) for m in output.options for v in m.unit_mix.values())


def test_real_path_falls_back_to_mock_without_llm(monkeypatch) -> None:
    # force the real path with no usable LLM (no key / SDK) -> must not raise,
    # must degrade to the mock so the end-to-end pipeline keeps working.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    output = generate(ENVELOPE, use_mock=False)
    assert isinstance(output, MassingOutput)
    assert len(output.options) >= 1


def test_envelope_to_raw_round_trips_fields() -> None:
    raw = pipeline.envelope_to_raw(ENVELOPE)
    assert raw["parcel_id"] == "test"
    assert raw["max_height_m"] == 30.0
    assert raw["setbacks"] == {"north": 3.0, "south": 0.0, "east": 1.5, "west": 1.5}
    assert raw["footprint_polygon"][0] == [0, 0]
    assert raw["parking_minimum"] == 0


def test_spec_to_massing_maps_tower_spec() -> None:
    art = pipeline.RenderArtifacts(three_d_uri="file:///tmp/x.glb", facade_renders=["a.png"])
    m = pipeline.spec_to_massing(TOWER_SPEC, ENVELOPE, "market", art)
    assert m.massing_id == "test-market"
    assert m.height_m == 52.0
    assert m.total_gfa_m2 == 14400.0
    # unit_mix keys are normalised to the contract's compact codes, values int
    assert m.unit_mix == {"studio": 20, "1br": 40, "2br": 28, "3br": 8, "penthouse": 4}
    assert m.retail_sqft > 0
    assert m.three_d_uri == "file:///tmp/x.glb"


def test_validator_passes_clean_spec_and_flags_broken_one() -> None:
    clean = json.loads((SPECS_DIR / "house_suburban.json").read_text())
    assert vb.validate(clean).count(vb.ERROR) == 0

    broken = json.loads((SPECS_DIR / "house_suburban.json").read_text())
    # side setbacks that exceed the frontage leave no buildable width -> error
    broken["setbacks_m"]["side_yard_east"] = 999.0
    assert vb.validate(broken).count(vb.ERROR) >= 1


def test_render_spec_plotly_fallback_writes_html(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("plotly")
    # route outputs to a temp dir so the test leaves no artifacts
    monkeypatch.setattr(pipeline, "OUTPUT_DIR", tmp_path)
    house = json.loads((SPECS_DIR / "house_suburban.json").read_text())
    art = pipeline.render_spec(house, "house-test", mode="plotly")
    assert art.three_d_uri.endswith(".html")
    assert Path(art.three_d_uri).exists()
