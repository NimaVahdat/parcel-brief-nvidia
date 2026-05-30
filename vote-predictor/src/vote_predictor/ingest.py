"""Build the precedent corpus from Toronto's Development Applications open dataset.

This replaces the agenda-title scrape: the open dataset (CKAN, no Akamai, plain
HTTP) carries the project DESCRIPTION (storeys, units, use) — the features that
actually predict outcomes — plus a clean STATUS we can label, across ~26k records.

We keep records with a decided outcome (approved / refused), focus on major
development applications, and balance the classes so the backtest is non-trivial.
The embedded `text` is the DESCRIPTION (+ type/ward) and never contains the status,
so there is no label leakage.

    vote-predictor fetch        # downloads + labels + writes data/precedents.jsonl
"""

from __future__ import annotations

import json

import httpx

from vote_predictor import config

CKAN = "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search"
RESOURCE_ID = "8907d8ed-c515-4ce9-b674-9f8c6eefcf0d"
CORPUS_PATH = config.DATA_DIR / "precedents.jsonl"

_APPROVED = {
    "Council Approved", "OMB Approved", "Draft Plan Approved",
    "Final Approval Completed", "Approved", "NOAC Issued", "OMB Partially Approved",
}
_REFUSED = {"Refused", "OMB Refused"}

# major development application types (the contentious, council-decided ones)
_TYPES = {
    "OZ": "Official Plan & Zoning By-law Amendment",
    "CD": "Condominium",
    "SB": "Plan of Subdivision",
    "RH": "Rental Housing",
    "ZBL": "Zoning By-law Amendment",
}


def _outcome(status: str) -> str | None:
    s = (status or "").strip()
    if s in _APPROVED:
        return "approved"
    if s in _REFUSED:
        return "refused"
    return None


def _address(r: dict) -> str:
    parts = [str(r.get(k, "")).strip() for k in
             ("STREET_NUM", "STREET_NAME", "STREET_TYPE", "STREET_DIRECTION")]
    return " ".join(p for p in parts if p and p.lower() != "none")


def fetch_records(limit: int = 32000) -> list[dict]:
    fields = ("APPLICATION_TYPE,STATUS,DESCRIPTION,STREET_NUM,STREET_NAME,STREET_TYPE,"
              "STREET_DIRECTION,WARD_NAME,WARD_NUMBER,DATE_SUBMITTED,APPLICATION#")
    with httpx.Client(timeout=120) as c:
        resp = c.get(CKAN, params={"resource_id": RESOURCE_ID, "fields": fields, "limit": limit})
        resp.raise_for_status()
        return resp.json()["result"]["records"]


def build_corpus(approved_per_refused: int = 3, min_desc_chars: int = 40) -> int:
    """Download, label, balance, and write data/precedents.jsonl. Returns count."""
    config.ensure_data_dir()
    records = fetch_records()

    approved, refused = [], []
    for r in records:
        if r.get("APPLICATION_TYPE") not in _TYPES:
            continue
        outcome = _outcome(r.get("STATUS", ""))
        desc = (r.get("DESCRIPTION") or "").strip()
        if not outcome or len(desc) < min_desc_chars:
            continue
        (approved if outcome == "approved" else refused).append((r, outcome, desc))

    # balance: keep all refused + an approved sample spread EVENLY across the date
    # range (not just the most recent), so the model can't separate on era/temporal
    # language instead of planning merit.
    approved.sort(key=lambda x: x[0].get("DATE_SUBMITTED") or "")
    n_keep = approved_per_refused * max(len(refused), 1)
    if len(approved) > n_keep > 0:
        step = len(approved) / n_keep
        approved = [approved[int(i * step)] for i in range(n_keep)]
    keep = refused + approved

    written = 0
    with CORPUS_PATH.open("w", encoding="utf-8") as out:
        for r, outcome, desc in keep:
            app_type = _TYPES.get(r["APPLICATION_TYPE"], r["APPLICATION_TYPE"])
            ward = (r.get("WARD_NAME") or "").strip()
            address = _address(r)
            year = int((r.get("DATE_SUBMITTED") or "0")[:4] or 0)
            text = f"{app_type} at {address}, {ward}: {desc}"
            out.write(json.dumps({
                "precedent_id": r.get("APPLICATION#") or f"app-{written}",
                "text": text, "outcome": outcome, "ward": str(r.get("WARD_NUMBER", "")),
                "committee": "", "year": year, "app_type": app_type,
                "address": address, "votes": {},
            }, ensure_ascii=False) + "\n")
            written += 1
    return written
