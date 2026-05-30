"""Unit tests for project-level feature engineering."""

from vote_predictor.features import AS_OF_RIGHT_HEIGHT_M, build_features


def test_build_features_derives_shares_and_flags():
    """build_features derives affordable share, retail flag, and height-over ratio."""
    feats = build_features(
        {
            "height_m": 60.0,
            "total_units": 100,
            "affordable_units": 25,
            "retail_sqft": 1500.0,
            "requested_variances": ["height", "density"],
            "neighborhood": "Parkdale",
        }
    )
    assert feats.affordable_share == 0.25
    assert feats.retail_flag == 1.0
    assert feats.requested_variances_count == 2
    assert feats.height_over_ratio == (60.0 - AS_OF_RIGHT_HEIGHT_M) / AS_OF_RIGHT_HEIGHT_M


def test_build_features_handles_json_string_variances_and_zero_units():
    """build_features tolerates JSON-string variances and avoids divide-by-zero."""
    feats = build_features(
        {
            "height_m": 0.0,
            "total_units": 0,
            "affordable_units": 0,
            "retail_sqft": 0.0,
            "requested_variances": '["a"]',
        }
    )
    assert feats.affordable_share == 0.0
    assert feats.retail_flag == 0.0
    assert feats.requested_variances_count == 1
    assert feats.height_over_ratio == 0.0
