"""CKAN source: the Toronto Open Data "Development Applications (AIC)" corpus.

Pulls the application universe the vote-predictor grounds on, over the plain-HTTP CKAN
datastore API (no Akamai, no browser). Two facts from the Phase-0 probe shape this module:

* The datastore is **event-level** — ~26k rows resolve to ~8.5k distinct applications. We
  dedup on ``FOLDERRSN`` (100% populated, 1:1 with ``APPLICATION#``) so the corpus is one
  row per application, not a triple-count.
* AIC carries no structured height/units — those live in the free-text ``DESCRIPTION``. We
  best-effort parse storeys/units from it so precedent features are non-degenerate; at
  inference the real features come from the caller via Contract 1.

``datastore_search_sql`` is disabled on this hardened instance, so all dedup is client-side.
"""

from __future__ import annotations

import json
import re

import pandas as pd

from vote_predictor import config
from vote_predictor.normalize import normalize_address

#: STATUS ranked by how decision-bearing it is, so dedup keeps the most informative event
#: per application (a council/tribunal decision beats an in-flight or closed snapshot).
_STATUS_PRIORITY = {
    "Council Approved": 100,
    "Approved": 95,
    "Refused": 95,
    "OMB Approved": 80,
    "OMB Refused": 80,
    "OMB Partially Approved": 78,
    "OMB Appeal": 70,
    "Appeal Received": 68,
    "Draft Plan Approved": 60,
    "Final Approval Completed": 58,
    "NOAC Issued": 40,
    "Closed": 30,
    "Circulated": 20,
    "Under Review": 15,
    "Application Received": 10,
}

#: Pull storeys ("9-storey", "9 storeys") from a free-text description.
_STOREY_RE = re.compile(r"(\d{1,3})\s*[- ]?\s*stor(?:e?y|eys|ies)", re.IGNORECASE)
#: Pull a unit count ("120 units", "120 residential units", "120 dwelling units").
_UNITS_RE = re.compile(r"(\d{1,4})\s+(?:residential\s+|dwelling\s+|rental\s+)?units", re.IGNORECASE)
#: Approximate metres per storey for converting a storey count to a height.
_METRES_PER_STOREY = 3.1


def normalize_application_number(value: str | None) -> str:
    """Normalize a Toronto planning file number for exact cross-system matching.

    Collapses internal whitespace to single spaces, upper-cases, and maps historical
    district codes (e.g. ``TEY`` -> ``STE``) to their current canonical form, so the
    ``APPLICATION#`` from the AIC datastore and the "Planning Application Number" parsed
    from a staff-report PDF compare equal.

    Args:
        value (str | None): A raw application number in any spacing/casing.

    Returns:
        str: The normalized ``'YY NNNNNN DDD WW TT'`` string, or ``""`` if not parseable.
    """
    if not value:
        return ""
    tokens = str(value).upper().split()
    if len(tokens) >= 5:
        tokens[2] = config.DISTRICT_ALIASES.get(tokens[2], tokens[2])
    return " ".join(tokens)


def _parse_description(description: str | None) -> dict:
    """Best-effort extraction of storeys/units from a free-text application description.

    Args:
        description (str | None): The AIC ``DESCRIPTION`` prose.

    Returns:
        dict: ``height_m`` and ``total_units`` (0.0/0 when not stated). Approximate — the
        authoritative features arrive via Contract 1 at inference time.
    """
    text = description if isinstance(description, str) else ""
    storey_match = _STOREY_RE.search(text)
    units_match = _UNITS_RE.search(text)
    height_m = float(int(storey_match.group(1)) * _METRES_PER_STOREY) if storey_match else 0.0
    total_units = int(units_match.group(1)) if units_match else 0
    return {"height_m": height_m, "total_units": total_units}


def _compose_address(record: dict) -> str:
    """Compose a single address string from the AIC street component columns.

    Args:
        record (dict): One AIC datastore record.

    Returns:
        str: A normalized ``"NUM NAME TYPE DIR"`` address (extra spaces collapsed).
    """
    parts = [
        str(record.get("STREET_NUM", "") or "").strip(),
        str(record.get("STREET_NAME", "") or "").strip(),
        str(record.get("STREET_TYPE", "") or "").strip(),
        str(record.get("STREET_DIRECTION", "") or "").strip(),
    ]
    return normalize_address(" ".join(p for p in parts if p))


def fetch_applications_raw(max_pages: int | None = None) -> pd.DataFrame:
    """Page the AIC datastore over plain HTTP into a raw, event-level DataFrame.

    Args:
        max_pages (int | None): Cap the number of pages pulled (each up to
            ``config.CKAN_PAGE_SIZE`` rows); ``None`` pulls the full corpus.

    Returns:
        pandas.DataFrame: Raw AIC records (event-level; not yet deduped).

    Raises:
        httpx.HTTPError: If a datastore request fails.
        RuntimeError: If the datastore returns no records.
    """
    import httpx

    records: list[dict] = []
    offset = 0
    page = 0
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        while True:
            response = client.get(
                config.CKAN_DATASTORE_SEARCH,
                params={
                    "resource_id": config.AIC_RESOURCE_ID,
                    "limit": config.CKAN_PAGE_SIZE,
                    "offset": offset,
                },
            )
            response.raise_for_status()
            batch = response.json()["result"]["records"]
            records.extend(batch)
            page += 1
            offset += config.CKAN_PAGE_SIZE
            if len(batch) < config.CKAN_PAGE_SIZE or (max_pages and page >= max_pages):
                break
    if not records:
        raise RuntimeError("CKAN AIC datastore returned no records.")
    return pd.DataFrame(records)


def dedup_and_normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """Collapse event-level AIC rows to one row per application and map to the model schema.

    Dedups on ``FOLDERRSN`` keeping the most decision-bearing ``STATUS`` per application,
    normalizes the application number, derives the committee from the district code, and
    best-effort parses height/units from the description.

    Args:
        raw (pandas.DataFrame): Raw AIC records from ``fetch_applications_raw``.

    Returns:
        pandas.DataFrame: One row per application with the columns the rest of the component
        expects (``application_id``, ``committee``, ``neighborhood``, features, ``status``,
        ``application_date``, plus join aids ``folder_rsn``, ``address``, ``ward_number``).
    """
    work = raw.copy()
    work["_status_priority"] = (
        work.get("STATUS", pd.Series(index=work.index, dtype=str)).map(_STATUS_PRIORITY).fillna(0)
    )
    work = work.sort_values("_status_priority", ascending=False)
    work = work.drop_duplicates(subset=["FOLDERRSN"], keep="first")

    rows: list[dict] = []
    for record in work.to_dict("records"):
        app_no = normalize_application_number(record.get("APPLICATION#"))
        tokens = app_no.split()
        district = tokens[2] if len(tokens) >= 5 else ""
        parsed = _parse_description(record.get("DESCRIPTION"))
        ward_name = str(record.get("WARD_NAME", "") or "").strip()
        rows.append(
            {
                "application_id": app_no,
                "folder_rsn": str(record.get("FOLDERRSN", "") or ""),
                "parcel_id": str(record.get("FOLDERRSN", "") or app_no),
                "agenda_item_id": None,  # filled by the crosswalk
                "application_type": str(record.get("APPLICATION_TYPE", "") or ""),
                "committee": config.COMMITTEE_BY_DISTRICT.get(district, ""),
                "neighborhood": ward_name,
                "ward_number": str(record.get("WARD_NUMBER", "") or "").strip(),
                "ward_name": ward_name,
                "ward_councillor_id": None,  # resolved via the roster crosswalk
                "address": _compose_address(record),
                "status": str(record.get("STATUS", "") or ""),
                "height_m": parsed["height_m"],
                "total_units": parsed["total_units"],
                "affordable_units": 0,
                "retail_sqft": 0.0,
                "use_mix": json.dumps({"residential": 1.0}),
                "requested_variances": json.dumps([]),
                "description": str(record.get("DESCRIPTION", "") or ""),
                "application_date": str(record.get("DATE_SUBMITTED", "") or "")[:10],
            }
        )
    return pd.DataFrame(rows)


def fetch_applications(max_pages: int | None = None) -> pd.DataFrame:
    """Fetch and normalize the AIC application corpus (one row per application).

    Args:
        max_pages (int | None): Cap pages pulled (for smoke tests); ``None`` = full corpus.

    Returns:
        pandas.DataFrame: The deduped, model-schema application table.

    Raises:
        httpx.HTTPError: If a datastore request fails.
        RuntimeError: If the datastore returns no records.
    """
    return dedup_and_normalize(fetch_applications_raw(max_pages=max_pages))
