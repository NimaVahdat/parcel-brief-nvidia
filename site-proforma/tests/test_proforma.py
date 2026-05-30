"""Offline tests for the DCF: cost scaling, IRR direction, sensitivities."""

from site_proforma import lookup
from site_proforma.proforma import calculate
from site_proforma.schemas import Massing

_SITE = lookup("43.6486_-79.3806")  # downtown


def _massing(gfa=8000.0, units=None, affordable=0, retail=2000) -> Massing:
    return Massing(
        massing_id="m", height_m=40.0, total_gfa_m2=gfa,
        unit_mix=units or {"studio": 10, "1br": 40, "2br": 30, "3br": 10},
        retail_sqft=retail, affordable_units=affordable,
        three_d_uri="mock://", facade_renders=[],
    )


def test_cost_scales_with_gfa() -> None:
    small = calculate(_massing(gfa=5000), _SITE).construction_cost
    big = calculate(_massing(gfa=15000), _SITE).construction_cost
    assert big > small > 0


def test_sensitivities_present_and_shaped() -> None:
    m = calculate(_massing(), _SITE)
    keys = {"rate_+100bp", "rate_-100bp", "rent_-10pct", "rent_+10pct", "stabilization_+6mo"}
    assert set(m.sensitivities) == keys
    for v in m.sensitivities.values():
        assert "irr_5y" in v and "irr_10y" in v


def test_higher_rent_higher_irr() -> None:
    m = calculate(_massing(), _SITE)
    assert m.sensitivities["rent_+10pct"]["irr_5y"] >= m.sensitivities["rent_-10pct"]["irr_5y"]


def test_more_affordable_lowers_rent() -> None:
    market = calculate(_massing(affordable=0), _SITE).projected_annual_rent
    affordable = calculate(_massing(affordable=40), _SITE).projected_annual_rent
    assert affordable < market   # affordable units rent below market


def test_irr_is_finite_float() -> None:
    m = calculate(_massing(), _SITE)
    assert isinstance(m.irr_5y, float) and -1.0 <= m.irr_5y <= 2.0
