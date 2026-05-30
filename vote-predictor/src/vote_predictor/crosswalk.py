"""The crosswalk: link a development application to the recorded votes cast on it.

This is the linchpin the Phase-0 probe identified. CKAN AIC and TMMIS share no key, so the
link is a three-hop chain — deterministic at its ends, scrape-bound in its middle:

    application_id (AIC APPLICATION#)
      └─[exact: the same number printed in the staff-report PDF]→ staff report + agenda item
                                                                  └─[exact: item id]→ vote rows

When the staff-report bridge is missing, we fall back to a fuzzy address + committee + date-
window match between the TMMIS item title and the AIC address, accepted only when unique.
Every link carries a ``join_confidence`` so the panel can down-weight or abstain on weak
links. Building this crosswalk — rather than assuming a shared ``application_id`` column — is
what lets the real (non-synthetic) training table actually join (fixes the D1 defect).
"""

from __future__ import annotations

import re

import pandas as pd
from rapidfuzz import fuzz, process

from vote_predictor import config
from vote_predictor.normalize import normalize_address

_TITLE_ADDRESS_RE = re.compile(r"^\s*(\d[\w\s\-]*?)(?:\s+[-–]\s+|$)")


def extract_address_from_title(title: str) -> str:
    """Extract the leading street address from a TMMIS agenda item title.

    Item titles for development items lead with the site address, e.g.
    ``"929 Queen Street East - Official Plan Amendment"``.

    Args:
        title (str): The agenda item title.

    Returns:
        str: The normalized leading address, or ``""`` if the title does not start with one.
    """
    match = _TITLE_ADDRESS_RE.match(str(title or ""))
    return normalize_address(match.group(1)) if match else ""


def _date_window_mask(submitted: pd.Series, meeting_date) -> pd.Series:
    """Vectorized mask of applications whose submission precedes a meeting by a plausible lag.

    Lenient where either date is missing, so a strong address match is not discarded for want
    of a date. Computed once per item over the whole candidate pool rather than per-pair.

    Args:
        submitted (pandas.Series): Parsed application submission datetimes (NaT allowed).
        meeting_date: The council/committee meeting date (string or NaT).

    Returns:
        pandas.Series: Boolean mask aligned to ``submitted``.
    """
    met = pd.to_datetime(meeting_date, errors="coerce")
    if pd.isna(met):
        return pd.Series(True, index=submitted.index)
    months = (met - submitted).dt.days / 30.4
    low, high = config.DATE_WINDOW_MONTHS
    return months.between(low, high) | submitted.isna()


def _exact_appnum_links(apps: pd.DataFrame, staff_recs: pd.DataFrame) -> list[dict]:
    """Build high-confidence links where a staff report's application number matches AIC.

    Args:
        apps (pandas.DataFrame): The deduped application table (``application_id``).
        staff_recs (pandas.DataFrame): Staff recs with ``application_id`` + ``agenda_item_id``.

    Returns:
        list[dict]: One link row per (application, agenda item) exact match.
    """
    app_ids = set(apps["application_id"].dropna())
    links: list[dict] = []
    for rec in staff_recs.to_dict("records"):
        aid = rec.get("application_id")
        item = rec.get("agenda_item_id")
        if aid and item and aid in app_ids:
            links.append(
                {
                    "application_id": aid,
                    "agenda_item_id": str(item),
                    "backgroundfile": rec.get("report_uri", ""),
                    "join_confidence": config.JOIN_CONFIDENCE_LEVELS["exact_appnum"],
                    "join_method": "exact_appnum",
                }
            )
    return links


def _fuzzy_address_links(
    apps: pd.DataFrame, vote_items: pd.DataFrame, linked_items: set[str]
) -> list[dict]:
    """Build medium-confidence links via address + committee + date window, unique-only.

    Args:
        apps (pandas.DataFrame): The deduped application table (with ``address``, ``committee``,
            ``application_date``).
        vote_items (pandas.DataFrame): One row per agenda item (``agenda_item_id``,
            ``item_title``, ``committee``, ``meeting_date``).
        linked_items (set[str]): Agenda item ids already linked exactly (skipped here).

    Returns:
        list[dict]: One link row per uniquely-matched agenda item.
    """
    apps = apps.copy()
    apps["_submitted"] = pd.to_datetime(apps["application_date"], errors="coerce")
    links: list[dict] = []
    for item in vote_items.to_dict("records"):
        item_id = str(item.get("agenda_item_id", "") or "")
        if not item_id or item_id in linked_items:
            continue
        address = extract_address_from_title(item.get("item_title", ""))
        if not address:
            continue
        committee = item.get("committee", "")
        pool = apps[apps["committee"] == committee] if committee else apps
        if pool.empty:  # e.g. a City Council adoption — the district committee won't match
            pool = apps
        pool = pool[_date_window_mask(pool["_submitted"], item.get("meeting_date", ""))]
        if pool.empty:
            continue
        ids = pool["application_id"].tolist()
        choices = pool["address"].fillna("").tolist()
        # rapidfuzz's batch matcher (C-optimized) over the whole pool, top 2 for the
        # uniqueness guard: accept only when the best match clears the threshold AND strictly
        # beats the runner-up (so two equally-good addresses at one site abstain).
        matches = process.extract(address, choices, scorer=fuzz.token_sort_ratio, limit=2)
        if not matches:
            continue
        best = matches[0]
        unique = len(matches) == 1 or matches[1][1] < best[1]
        if best[1] >= config.ADDRESS_FUZZY_THRESHOLD and unique:
            links.append(
                {
                    "application_id": ids[best[2]],
                    "agenda_item_id": item_id,
                    "backgroundfile": "",
                    "join_confidence": config.JOIN_CONFIDENCE_LEVELS["address_ward_date"],
                    "join_method": "address_ward_date",
                }
            )
    return links


def build_crosswalk(
    apps: pd.DataFrame, staff_recs: pd.DataFrame | None, votes: pd.DataFrame
) -> pd.DataFrame:
    """Build the application ↔ agenda-item ↔ vote crosswalk with per-link confidence.

    Args:
        apps (pandas.DataFrame): Deduped applications (``application_id``, ``address``,
            ``committee``, ``application_date``).
        staff_recs (pandas.DataFrame | None): Staff recs bridging app number -> agenda item.
        votes (pandas.DataFrame): Recorded votes (``agenda_item_id``, ``item_title``,
            ``committee``, ``meeting_date``).

    Returns:
        pandas.DataFrame: Columns ``application_id``, ``agenda_item_id``, ``backgroundfile``,
        ``join_confidence``, ``join_method`` — one row per resolved link.
    """
    links: list[dict] = []
    if staff_recs is not None and not staff_recs.empty:
        links.extend(_exact_appnum_links(apps, staff_recs))
    linked_items = {link["agenda_item_id"] for link in links}

    if not votes.empty and "agenda_item_id" in votes:
        vote_items = votes.sort_values("agenda_item_id").drop_duplicates(subset=["agenda_item_id"])[
            ["agenda_item_id", "item_title", "committee", "meeting_date"]
        ]
        links.extend(_fuzzy_address_links(apps, vote_items, linked_items))

    columns = [
        "application_id",
        "agenda_item_id",
        "backgroundfile",
        "join_confidence",
        "join_method",
    ]
    return pd.DataFrame(links, columns=columns)


def apply_crosswalk(
    apps: pd.DataFrame, votes: pd.DataFrame, crosswalk: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stamp ``agenda_item_id`` onto applications and ``application_id`` onto votes.

    Resolves the real link so the downstream training table can join on a shared key (the
    synthetic generator stamped these columns for free; real data needs this step).

    Args:
        apps (pandas.DataFrame): The application table.
        votes (pandas.DataFrame): The votes table.
        crosswalk (pandas.DataFrame): The crosswalk from ``build_crosswalk``.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]: ``(apps, votes)`` with the join keys and a
        ``join_confidence`` column on votes (None where unlinked).
    """
    apps_out = apps.copy()
    votes_out = votes.copy()
    if crosswalk.empty:
        apps_out["agenda_item_id"] = None
        votes_out["application_id"] = None
        votes_out["join_confidence"] = None
        return apps_out, votes_out

    item_by_app = crosswalk.drop_duplicates(subset=["application_id"]).set_index("application_id")[
        "agenda_item_id"
    ]
    by_item = crosswalk.drop_duplicates(subset=["agenda_item_id"]).set_index("agenda_item_id")
    apps_out["agenda_item_id"] = apps_out["application_id"].map(item_by_app)
    votes_out["application_id"] = votes_out["agenda_item_id"].map(by_item["application_id"])
    votes_out["join_confidence"] = votes_out["agenda_item_id"].map(by_item["join_confidence"])
    return apps_out, votes_out


def coverage_report(apps: pd.DataFrame, crosswalk: pd.DataFrame) -> dict:
    """Summarize how much of the application corpus actually links to a recorded vote.

    Args:
        apps (pandas.DataFrame): The deduped application table.
        crosswalk (pandas.DataFrame): The crosswalk from ``build_crosswalk``.

    Returns:
        dict: ``n_applications``, ``n_linked``, ``coverage`` (fraction), and the link-method
        breakdown — the empirical answer to the Phase-0 "how low is coverage" question.
    """
    n_apps = int(apps["application_id"].nunique())
    linked = int(crosswalk["application_id"].nunique()) if not crosswalk.empty else 0
    methods = crosswalk["join_method"].value_counts().to_dict() if not crosswalk.empty else {}
    return {
        "n_applications": n_apps,
        "n_linked": linked,
        "coverage": round(linked / n_apps, 4) if n_apps else 0.0,
        "by_method": methods,
    }
