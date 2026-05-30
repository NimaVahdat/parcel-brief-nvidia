"""Feature engineering: raw applications + votes → XGBoost-ready feature matrix."""

from dataclasses import dataclass


@dataclass
class FeatureSpec:
    """Canonical feature set the trained model expects."""

    # numeric
    height_m: float
    total_units: int
    affordable_units: int
    affordable_share: float
    retail_sqft: float
    requested_variances_count: int

    # one-hot encoded at training time
    neighborhood: str
    committee: str


def build_features(application: dict) -> FeatureSpec:
    """Convert a raw application dict to a FeatureSpec.

    TODO: handle missing fields, encode use_mix into numeric columns, derive
    affordable_share, normalize neighborhoods to a canonical list.
    """
    raise NotImplementedError("Implement feature extraction from raw application data.")
