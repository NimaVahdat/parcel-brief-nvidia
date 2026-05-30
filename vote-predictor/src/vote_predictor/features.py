"""Feature engineering: a raw application -> the project-level features the model uses.

These are the features derivable from a single application (the Contract 1
``ApplicationFeatures`` shape). The per-councillor pieces — historical propensity, the
staff signal, and the ward flag — are combined with these in ``panel.py`` to form the full
feature vector, because they depend on *who* is voting, not just *what* is proposed.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

#: As-of-right height (m) used as the reference for the "how far over" feature. A real
#: implementation would read this per-parcel from the zoning layer; absent that, a single
#: midrise reference keeps the feature meaningful and monotonic.
AS_OF_RIGHT_HEIGHT_M = 30.0


@dataclass
class FeatureSpec:
    """Project-level features derived from one application.

    Attributes:
        height_m (float): Proposed height in metres.
        total_units (int): Total residential units.
        affordable_units (int): Affordable units included.
        affordable_share (float): Affordable units / total units, in [0, 1].
        retail_sqft (float): Ground-floor retail area.
        retail_flag (float): 1.0 if any retail is proposed, else 0.0.
        requested_variances_count (int): Number of requested zoning variances.
        height_over_ratio (float): Fractional height over as-of-right (>= 0).
        neighborhood (str): Neighborhood name (one-hot encoded downstream if used).
    """

    height_m: float
    total_units: int
    affordable_units: int
    affordable_share: float
    retail_sqft: float
    retail_flag: float
    requested_variances_count: int
    height_over_ratio: float
    neighborhood: str

    def to_dict(self) -> dict:
        """Return the feature spec as a plain dict.

        Returns:
            dict: Field-name -> value mapping for all features.
        """
        return asdict(self)


def _coerce_variances(value) -> int:
    """Coerce a requested-variances field (list or JSON string) to a count.

    Args:
        value: Either a list of variance names, a JSON-encoded list string, or None.

    Returns:
        int: The number of requested variances (0 if unparseable or empty).
    """
    if value is None:
        return 0
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return len(parsed) if isinstance(parsed, list) else 0
        except (json.JSONDecodeError, TypeError):
            return 0
    return 0


def build_features(application: dict) -> FeatureSpec:
    """Convert a raw application dict into a project-level FeatureSpec.

    Accepts the Contract 1 ``ApplicationFeatures`` fields (also tolerant of parquet rows
    where list fields arrive as JSON strings). Derives affordable share, the retail flag,
    and the height-over-as-of-right ratio, and is defensive about missing/zero fields.

    Args:
        application (dict): Application fields — at minimum ``height_m``, ``total_units``,
            ``affordable_units``, ``retail_sqft``; optionally ``requested_variances`` and
            ``neighborhood``.

    Returns:
        FeatureSpec: The derived project-level features.
    """
    total_units = int(application.get("total_units", 0) or 0)
    affordable_units = int(application.get("affordable_units", 0) or 0)
    affordable_share = (affordable_units / total_units) if total_units > 0 else 0.0
    retail_sqft = float(application.get("retail_sqft", 0.0) or 0.0)
    height_m = float(application.get("height_m", 0.0) or 0.0)
    height_over_ratio = max(0.0, (height_m - AS_OF_RIGHT_HEIGHT_M) / AS_OF_RIGHT_HEIGHT_M)

    return FeatureSpec(
        height_m=height_m,
        total_units=total_units,
        affordable_units=affordable_units,
        affordable_share=affordable_share,
        retail_sqft=retail_sqft,
        retail_flag=1.0 if retail_sqft > 0 else 0.0,
        requested_variances_count=_coerce_variances(application.get("requested_variances")),
        height_over_ratio=height_over_ratio,
        neighborhood=str(application.get("neighborhood", "") or ""),
    )
