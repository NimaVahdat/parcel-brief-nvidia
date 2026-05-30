"""Assemble a labeled vote table by joining applications, votes, and staff recs.

Produces one row per (application, councillor) with the engineered project features, the
staff signal, the ward flag, and the binary label (councillor voted Yes). Used by the
evaluation harness and for quick base-rate reporting. The agent itself grounds on the
councillor profiles and similar cases from ``retrieval``, not on this flat table.
"""

from __future__ import annotations

import pandas as pd

from vote_predictor import config
from vote_predictor.features import build_features


def build_training_table() -> pd.DataFrame:
    """Join the processed parquet sources into a per-(application, councillor) table.

    Returns:
        pandas.DataFrame: Columns include ``application_id``, ``councillor_id``,
        ``committee``, ``meeting_date``, the project features, ``staff_signal``,
        ``ward_flag``, and the integer ``label`` (1 = voted Yes).

    Raises:
        FileNotFoundError: If the processed parquet inputs are missing (run ingest first).
    """
    for path in (config.APPLICATIONS_PARQUET, config.VOTES_PARQUET, config.STAFF_RECS_PARQUET):
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}. Run `vote-predictor ingest` first.")

    apps = pd.read_parquet(config.APPLICATIONS_PARQUET)
    votes = pd.read_parquet(config.VOTES_PARQUET)
    recs = pd.read_parquet(config.STAFF_RECS_PARQUET)[["application_id", "recommendation"]]

    # On real data only crosswalk-linked votes carry an application_id; unlinked votes have
    # no application to attach to, so drop them rather than silently producing NaN-keyed rows.
    if "application_id" in votes:
        votes = votes.dropna(subset=["application_id"])
    merged = votes.merge(apps, on="application_id", suffixes=("", "_app")).merge(
        recs, on="application_id", how="left"
    )
    merged["recommendation"] = merged["recommendation"].fillna("unknown")
    if merged.empty:
        raise RuntimeError(
            "Training table is empty after the application↔vote join. On real data this means "
            "the crosswalk linked no votes — check ingest coverage (see crosswalk.coverage_report)."
        )

    rows: list[dict] = []
    for record in merged.to_dict("records"):
        feats = build_features(record)
        ward_flag = 1.0 if record.get("ward_councillor_id") == record.get("councillor_id") else 0.0
        rows.append(
            {
                "application_id": record["application_id"],
                "councillor_id": record["councillor_id"],
                "committee": record.get("committee", ""),
                "meeting_date": str(record.get("meeting_date", "")),
                "affordable_share": feats.affordable_share,
                "retail_flag": feats.retail_flag,
                "variance_count": feats.requested_variances_count,
                "height_over_ratio": feats.height_over_ratio,
                "staff_signal": config.STAFF_SIGNAL_MAP.get(record["recommendation"], 0.0),
                "ward_flag": ward_flag,
                "label": 1 if str(record["vote"]).strip().lower() == "yes" else 0,
            }
        )
    table = pd.DataFrame(rows)
    table.to_parquet(config.TRAINING_TABLE_PARQUET, index=False)
    return table


def compute_base_rates(table: pd.DataFrame) -> dict:
    """Compute naive baseline statistics the agent should beat.

    Args:
        table (pandas.DataFrame): A table from ``build_training_table``.

    Returns:
        dict: ``overall_yes_rate``, ``n_votes``, ``n_items``, and ``contested_fraction``
        (share of items whose per-councillor votes were not unanimous).
    """
    by_item = table.groupby("application_id")["label"]
    contested = (by_item.mean().between(0.0, 1.0, inclusive="neither")).mean()
    return {
        "overall_yes_rate": float(table["label"].mean()),
        "n_votes": int(len(table)),
        "n_items": int(table["application_id"].nunique()),
        "contested_fraction": float(contested),
    }
