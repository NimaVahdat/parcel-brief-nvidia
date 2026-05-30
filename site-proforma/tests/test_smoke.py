"""Smoke test."""

from site_proforma import calculate, lookup
from site_proforma.schemas import FinancialModel, Massing, SiteData


def test_lookup_returns_site_data() -> None:
    site = lookup("test-parcel")
    assert isinstance(site, SiteData)
    assert site.zoning_envelope.parcel_id == "test-parcel"


def test_calculate_returns_financial_model() -> None:
    site = lookup("test-parcel")
    massing = Massing(
        massing_id="m1",
        height_m=30.0,
        total_gfa_m2=5000.0,
        unit_mix={"1br": 30, "2br": 20},
        retail_sqft=1000,
        affordable_units=5,
        three_d_uri="mock://",
        facade_renders=[],
    )
    model = calculate(massing, site)
    assert isinstance(model, FinancialModel)
    assert model.construction_cost > 0
    assert model.irr_5y is not None
