"""Offline tests for site lookup: id parsing, location-aware envelope, transit."""

from site_proforma.site import _nearest_transit_m, _parse_parcel_id, lookup


def test_parse_parcel_id() -> None:
    assert _parse_parcel_id("43.65320_-79.38320") == (43.6532, -79.3832)
    assert _parse_parcel_id("not-a-coord") is None


def test_downtown_denser_than_outskirts() -> None:
    downtown = lookup("43.6486_-79.3806").zoning_envelope        # core
    outer = lookup("43.7700_-79.5000").zoning_envelope           # far NW
    assert downtown.max_height_m > outer.max_height_m
    assert downtown.max_fsi > outer.max_fsi


def test_transit_distance_real_and_positive() -> None:
    # near Union Station -> very small distance
    d = _nearest_transit_m(43.6453, -79.3806)
    assert 0 <= d < 200


def test_lookup_constraints_consistent() -> None:
    site = lookup("43.6486_-79.3806")
    assert site.constraints.parcel_id == site.zoning_envelope.parcel_id
    assert site.constraints.transit_distance_m >= 0
    # tall downtown envelope triggers a shadow-study rule
    assert site.constraints.sun_shadow_rules
