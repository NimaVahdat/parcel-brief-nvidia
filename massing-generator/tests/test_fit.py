"""Offline tests: massings fit the envelope and are internally consistent."""

from massing_generator import generate
from massing_generator.massing_fit import fit_massing, lot_area_m2
from massing_generator.schemas import ZoningEnvelope


def _downtown_envelope() -> ZoningEnvelope:
    # ~30 m square parcel in downtown Toronto (WGS84)
    lat, lon, d = 43.6486, -79.3806, 0.00018
    poly = [(lon - d, lat - d), (lon - d, lat + d), (lon + d, lat + d),
            (lon + d, lat - d), (lon - d, lat - d)]
    return ZoningEnvelope(
        parcel_id="43.6486_-79.3806", max_height_m=84.0, max_fsi=12.0,
        setbacks={"north": 3.0, "south": 0.0, "east": 1.5, "west": 1.5},
        permitted_uses=["residential", "retail", "office"], footprint_polygon=poly,
    )


def test_lot_area_reasonable() -> None:
    area = lot_area_m2(_downtown_envelope().footprint_polygon)
    assert 1000 < area < 3000   # ~36 m square ≈ ~1300 m²


def test_fit_respects_caps() -> None:
    f = fit_massing(max_height_m=84, max_fsi=12, lot_area=1000,
                    has_retail=True, gfa_fraction=1.0, affordable_share=0.0)
    assert f["height_m"] <= 84
    assert f["total_gfa_m2"] <= 12 * 1000 + 1


def test_units_consistent_with_gfa() -> None:
    f = fit_massing(max_height_m=84, max_fsi=12, lot_area=1000,
                    has_retail=True, gfa_fraction=1.0, affordable_share=0.15)
    units = sum(f["unit_mix"].values())
    gfa_per_unit = f["total_gfa_m2"] / units
    assert 60 <= gfa_per_unit <= 130    # realistic, not 214 m²/unit
    assert f["affordable_units"] <= units


def test_generate_options_fit_envelope() -> None:
    env = _downtown_envelope()
    out = generate(env)
    assert len(out.options) == 3
    for m in out.options:
        assert m.height_m <= env.max_height_m
        assert sum(m.unit_mix.values()) > 0
