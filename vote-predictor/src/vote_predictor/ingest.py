"""Ingestion: land the real sources to parquet, with an explicit offline synthetic mode.

The real path (default) pulls the three sources documented in the Phase-0 data-grounding
spec and resolves the link between them:

* **Applications** — CKAN AIC datastore (plain HTTP), deduped to one row per application.
* **Votes** — TMMIS recorded per-councillor votes, via the official CSV export (Playwright)
  or the non-Akamai mirror for seeding (``tmmis_source``).
* **Staff recommendations** — parsed from legdocs report PDFs (``staff_reports``); the
  agenda-page crawl that discovers each report's id and agenda item is Akamai-gated and runs
  on a machine that can reach TMMIS, so it is supplied as resolved links here.

The application↔vote link has no shared key, so ``crosswalk`` resolves it and stamps the join
keys onto both tables before they are written — which is what makes the real training table
actually join. ``generate_synthetic`` remains as an explicit ``--synthetic`` mode for CI and
the offline demo; its parquet schema matches the real pulls.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd

from vote_predictor import config
from vote_predictor.normalize import normalize_councillor_id  # re-exported for back-compat

logger = logging.getLogger(__name__)

#: Synthetic applications get monotonically increasing dates from this base, so the eval's
#: time-ordered 80/20 split is a true temporal partition (earlier train, later test).
_SYNTHETIC_BASE_DATE = date(2018, 1, 1)

__all__ = [
    "normalize_councillor_id",
    "fetch_staff_recommendation",
    "generate_synthetic",
    "ingest",
]


def fetch_staff_recommendation(application_id: str) -> str:
    """Look up the city planning staff recommendation for an application.

    Reads the locally ingested staff-recs table. Kept as the inference-time entry point so
    ``predict()`` can enrich an application without changing Contract 1. Returns ``"unknown"``
    (neutral) when no recommendation has been ingested.

    Args:
        application_id (str): The application id (or parcel id) to look up.

    Returns:
        str: A recommendation key understood by ``config.STAFF_SIGNAL_MAP``.
    """
    if not config.STAFF_RECS_PARQUET.exists():
        return "unknown"
    recs = pd.read_parquet(config.STAFF_RECS_PARQUET)
    match = recs[(recs["application_id"] == application_id) | (recs["parcel_id"] == application_id)]
    if match.empty:
        return "unknown"
    return str(match.iloc[0]["recommendation"])


def _ingest_real(
    terms: list[str] | None,
    seed_item_ids: list[str] | None,
    staff_links: list[tuple[str, str]] | None,
    max_pages: int | None,
    build_embeddings: bool,
) -> dict:
    """Pull the real sources, resolve the crosswalk, and write the processed parquet.

    Args:
        terms (list[str] | None): Council term ids to pull the official vote CSV for.
        seed_item_ids (list[str] | None): Agenda item ids to seed votes from the mirror.
        staff_links (list[tuple[str, str]] | None): ``(agenda_item_id, report_url)`` pairs to
            fetch and parse staff recommendations from.
        max_pages (int | None): Cap CKAN pages (for smoke pulls).
        build_embeddings (bool): Whether to build the embedding index after ingest.

    Returns:
        dict: An ingestion report (row counts + join coverage).
    """
    from vote_predictor import ckan_source, crosswalk, staff_reports, tmmis_source

    config.ensure_dirs()
    apps = ckan_source.fetch_applications(max_pages=max_pages)

    vote_frames: list[pd.DataFrame] = []
    if seed_item_ids:
        vote_frames.append(tmmis_source.fetch_votes_mirror(seed_item_ids))
    for term in terms or []:
        vote_frames.append(tmmis_source.fetch_member_votes_playwright(term))
    votes = (
        pd.concat([f for f in vote_frames if not f.empty], ignore_index=True)
        if any(not f.empty for f in vote_frames)
        else pd.DataFrame(columns=["agenda_item_id", "item_title", "committee", "meeting_date"])
    )

    staff_rows: list[dict] = []
    for item_id, url in staff_links or []:
        try:
            parsed = staff_reports.parse_staff_report(
                staff_reports.fetch_report_pdf(url), url, item_id
            )
        except Exception as exc:  # noqa: BLE001 - a single bad PDF should not abort the ingest
            logger.warning("Skipping staff report %s: %s", url, exc)
            parsed = None
        if parsed:
            staff_rows.append(parsed)
    staff = pd.DataFrame(staff_rows)

    xwalk = crosswalk.build_crosswalk(apps, staff if not staff.empty else None, votes)
    apps, votes = crosswalk.apply_crosswalk(apps, votes, xwalk)

    apps.to_parquet(config.APPLICATIONS_PARQUET, index=False)
    votes.to_parquet(config.VOTES_PARQUET, index=False)
    if not staff.empty:
        staff.to_parquet(config.STAFF_RECS_PARQUET, index=False)
    xwalk.to_parquet(config.CROSSWALK_PARQUET, index=False)

    if build_embeddings:
        from vote_predictor import embeddings

        try:
            embeddings.build_application_index(apps)
        except Exception as exc:  # noqa: BLE001 - embeddings are optional; ingest still succeeds
            logger.warning("Embedding index build failed (optional): %s", exc)

    report = crosswalk.coverage_report(apps, xwalk)
    report["n_votes"] = int(len(votes))
    report["n_votes_linked"] = (
        int(votes["application_id"].notna().sum()) if "application_id" in votes else 0
    )
    return report


def generate_synthetic(n_applications: int = 1500, seed: int = 7) -> None:
    """Generate a realistic, learnable synthetic dataset and write it to parquet.

    Builds councillors with latent pro/anti-development propensities across five community
    councils, samples applications with correlated staff recommendations, and draws
    per-councillor votes from a logistic ground-truth model. Lets the full predict/eval
    pipeline run offline; the parquet schema matches the real pulls (votes already carry the
    join key, so the crosswalk is unnecessary in this mode).

    Args:
        n_applications (int): Number of synthetic applications to generate.
        seed (int): RNG seed for reproducibility.

    Returns:
        None. Side effect only: writes applications/votes/staff_recs parquet files.
    """
    config.ensure_dirs()
    rng = np.random.default_rng(seed)

    committees = [
        "toronto-east-york",
        "north-york",
        "scarborough",
        "etobicoke-york",
        "city-council",
    ]
    councillors: list[dict] = []
    for committee in committees:
        for k in range(5):
            cid = f"{committee.split('-')[0]}{k}"
            councillors.append(
                {
                    "councillor_id": cid,
                    "committee": committee,
                    "propensity": float(rng.normal(0.4, 0.9)),
                }
            )
    councillors_by_committee: dict[str, list[dict]] = {c: [] for c in committees}
    for c in councillors:
        councillors_by_committee[c["committee"]].append(c)

    neighborhoods = [
        "Trinity-Bellwoods",
        "Rosedale",
        "Liberty Village",
        "Leslieville",
        "Yorkville",
        "The Annex",
        "Parkdale",
        "Riverdale",
        "Willowdale",
        "Scarborough Village",
    ]

    app_rows: list[dict] = []
    vote_rows: list[dict] = []
    rec_rows: list[dict] = []

    for i in range(n_applications):
        committee = committees[rng.integers(0, len(committees))]
        height_m = float(np.clip(rng.normal(40, 22), 8, 220))
        total_units = int(np.clip(rng.normal(120, 90), 4, 900))
        affordable_share = float(np.clip(rng.beta(1.5, 6), 0, 0.6))
        affordable_units = int(total_units * affordable_share)
        retail_sqft = float(max(0.0, rng.normal(2500, 2500)))
        variance_count = int(np.clip(rng.poisson(3), 0, 12))
        as_of_right_height = 30.0
        height_over_ratio = max(0.0, (height_m - as_of_right_height) / as_of_right_height)

        quality = 1.4 * affordable_share - 0.12 * variance_count - 0.35 * height_over_ratio
        rec_logit = 1.2 + 2.5 * quality + rng.normal(0, 0.8)
        rec_p = 1 / (1 + np.exp(-rec_logit))
        draw = rng.random()
        if draw < rec_p * 0.8:
            recommendation = "approve"
        elif draw < rec_p:
            recommendation = "approve_with_conditions"
        else:
            recommendation = "refuse"
        staff_signal = config.STAFF_SIGNAL_MAP[recommendation]

        application_id = f"SYN-{i:05d}"
        parcel_id = f"PARCEL-{i:05d}"
        app_date = (_SYNTHETIC_BASE_DATE + timedelta(days=i)).isoformat()
        meeting_date = (_SYNTHETIC_BASE_DATE + timedelta(days=i + 45)).isoformat()
        committee_members = councillors_by_committee[committee]
        ward_idx = int(rng.integers(0, len(committee_members)))

        app_rows.append(
            {
                "application_id": application_id,
                "parcel_id": parcel_id,
                "agenda_item_id": f"ITEM-{i:05d}",
                "committee": committee,
                "neighborhood": neighborhoods[rng.integers(0, len(neighborhoods))],
                "ward_councillor_id": committee_members[ward_idx]["councillor_id"],
                "height_m": height_m,
                "total_units": total_units,
                "affordable_units": affordable_units,
                "retail_sqft": retail_sqft,
                "use_mix": json.dumps({"residential": 0.85, "retail": 0.15}),
                "requested_variances": json.dumps(
                    ["height", "density"][: max(1, variance_count // 4)]
                ),
                "application_date": app_date,
                "address": f"{100 + i} SYNTHETIC AVE",
                "description": f"{total_units} unit {height_m:.0f}m residential development",
                "application_type": "OZ",
            }
        )
        rec_rows.append(
            {
                "application_id": application_id,
                "parcel_id": parcel_id,
                "agenda_item_id": f"ITEM-{i:05d}",
                "recommendation": recommendation,
                "report_uri": "",
            }
        )

        for m, member in enumerate(committee_members):
            ward_flag = 1.0 if m == ward_idx else 0.0
            # NOTE: these ground-truth coefficients deliberately mirror panel._FALLBACK_WEIGHTS
            # (staff 1.7, ward 0.9, affordable 1.3, variance -0.16, height_over -0.45) so the
            # deterministic fallback is *learnable* on synthetic data. This is why the synthetic
            # backtest (AUC ~0.88) flatters the heuristic while real Toronto votes (AUC ~0.57)
            # do not — the agreement there is by construction, not generalization. They are kept
            # as separate literals on purpose: sharing one constant would couple the predictor
            # to the simulator and hide exactly this caveat.
            logit = (
                member["propensity"]
                + 1.7 * staff_signal
                + 0.9 * ward_flag * (1 if staff_signal >= 0 else -1)
                + 1.3 * (affordable_share - 0.1)
                - 0.16 * variance_count
                - 0.45 * height_over_ratio
                + rng.normal(0, 0.6)
            )
            p_yes = 1 / (1 + np.exp(-logit))
            vote = "Yes" if rng.random() < p_yes else "No"
            vote_rows.append(
                {
                    "agenda_item_id": f"ITEM-{i:05d}",
                    "application_id": application_id,
                    "councillor_id": member["councillor_id"],
                    "committee": committee,
                    "vote": vote,
                    "meeting_date": meeting_date,
                    "item_title": f"{100 + i} Synthetic Avenue - Rezoning",
                }
            )

    pd.DataFrame(app_rows).to_parquet(config.APPLICATIONS_PARQUET, index=False)
    pd.DataFrame(vote_rows).to_parquet(config.VOTES_PARQUET, index=False)
    pd.DataFrame(rec_rows).to_parquet(config.STAFF_RECS_PARQUET, index=False)


def ingest(
    synthetic: bool = False,
    terms: list[str] | None = None,
    seed_item_ids: list[str] | None = None,
    staff_links: list[tuple[str, str]] | None = None,
    max_pages: int | None = None,
    build_embeddings: bool = True,
) -> dict | None:
    """Run ingestion into local parquet, choosing the real or synthetic source path.

    Args:
        synthetic (bool): When True, generate the offline synthetic dataset (CI/demo). When
            False (default), pull the real sources and resolve the crosswalk.
        terms (list[str] | None): Council term ids for the official vote CSV (real path).
        seed_item_ids (list[str] | None): Agenda item ids to seed votes from the mirror.
        staff_links (list[tuple[str, str]] | None): ``(agenda_item_id, report_url)`` pairs.
        max_pages (int | None): Cap CKAN pages (real path smoke pulls).
        build_embeddings (bool): Whether to build the embedding index (real path).

    Returns:
        dict | None: An ingestion report (real path) or None (synthetic path).

    Raises:
        ImportError: If the real path needs Playwright (vote CSV) and it is not installed.
        RuntimeError: If a real source returns no usable data.
    """
    config.ensure_dirs()
    if synthetic:
        generate_synthetic()
        return None
    return _ingest_real(terms, seed_item_ids, staff_links, max_pages, build_embeddings)


def main() -> None:
    """CLI entry point: ``python -m vote_predictor.ingest`` (synthetic for a safe default).

    Returns:
        None.
    """
    ingest(synthetic=True)


if __name__ == "__main__":
    main()
