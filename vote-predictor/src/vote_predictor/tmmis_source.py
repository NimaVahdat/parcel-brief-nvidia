"""TMMIS source: recorded per-councillor votes — the labels the predictor learns from.

Two access paths, both grounded in the Phase-0 probe:

* **Official Member Voting Record CSV** (the City's downloadable export). Its real schema is
  ``First Name, Last Name, Committee, Date/Time, Agenda Item #, Agenda Item Title,
  Motion Type, Vote, Result, Vote Description``. ``Vote`` includes ``Absent`` /
  ``Absent(Interest Declared)`` rows, which are dropped (a recused/absent member casts no
  directional vote). A single agenda item carries several motions; we keep the **main
  disposition** ("Adopt Item" / "Adopt Item as Amended") so the label is the vote on the
  item's outcome, not on an amendment.
* **Non-Akamai community mirror** — plain HTTP, used to seed items by id.

The CSV/HTML parsers are pure functions, fixture-tested without the network.
"""

from __future__ import annotations

import io
import re
from urllib.parse import urlencode

import pandas as pd

from vote_predictor import config
from vote_predictor.normalize import normalize_councillor_id

#: Canonical field -> the header synonyms seen across the official export and the mirror.
_CSV_HEADER_SYNONYMS = {
    "agenda_item_id": ["agenda item #", "agenda item number", "agenda item", "item", "item #"],
    "item_title": ["agenda item title", "title", "item title"],
    "motion": ["motion type", "motion", "type", "question"],
    "vote": ["vote", "vote cast", "value"],
    "result": ["result", "outcome"],
    "committee": ["committee", "decision body", "body"],
    "member": ["member", "name", "councillor", "member name"],
    "first_name": ["first name", "first"],
    "last_name": ["last name", "last", "surname"],
    "meeting_date": ["date/time", "date", "meeting date", "vote date"],
}

#: Agenda item id, e.g. 2024.TE12.5
_ITEM_ID_RE = re.compile(r"\b(20\d{2}\.[A-Z]{2}\d{1,3}\.\d{1,3})\b")
#: Votes that count as a directional recorded vote (everything else, incl. Absent, is dropped).
_DIRECTIONAL_VOTES = {"yes", "no"}


def _map_columns(columns: list[str]) -> dict[str, str]:
    """Map a CSV's actual headers to canonical field names via case-insensitive synonyms.

    Args:
        columns (list[str]): The raw column headers from the export.

    Returns:
        dict[str, str]: Canonical-field -> actual-column-name for every field found.
    """
    lowered = {str(c).strip().lower(): c for c in columns}
    mapping: dict[str, str] = {}
    for canonical, synonyms in _CSV_HEADER_SYNONYMS.items():
        for synonym in synonyms:
            if synonym in lowered:
                mapping[canonical] = lowered[synonym]
                break
    return mapping


def _committee_from_item_id(item_id: str) -> str:
    """Derive the committee slug from an agenda item id's body code.

    Args:
        item_id (str): An agenda item id like ``2024.TE12.5``.

    Returns:
        str: The committee slug, or ``""`` if the body code is unknown.
    """
    match = re.match(r"20\d{2}\.([A-Z]{2})", str(item_id) or "")
    return config.BODY_CODE_TO_COMMITTEE.get(match.group(1), "") if match else ""


def _resolve_committee(committee_value: str, item_id: str) -> str:
    """Resolve a committee slug from the CSV committee name, else the agenda item id.

    Args:
        committee_value (str): The raw ``Committee`` column value (full name).
        item_id (str): The agenda item id (fallback source of the body code).

    Returns:
        str: The committee slug (``""`` if neither resolves).
    """
    name = str(committee_value or "").strip().lower()
    if name in config.COMMITTEE_NAME_TO_SLUG:
        return config.COMMITTEE_NAME_TO_SLUG[name]
    return _committee_from_item_id(item_id)


def _is_main_motion(motion: str) -> bool:
    """Whether a motion's type marks the item's main disposition (not an amendment).

    Args:
        motion (str): The motion-type text.

    Returns:
        bool: True if it is a final-disposition motion.
    """
    return str(motion or "").strip().lower() in config.MAIN_MOTION_TYPES


def select_main_motion_rows(item_rows: pd.DataFrame) -> pd.DataFrame:
    """Reduce one agenda item's recorded-vote rows to its main disposition motion.

    Prefers rows whose motion type is a final disposition ("Adopt Item" / "Adopt the item");
    if none are present, falls back to the rows of the last motion in file order, so a member
    gets one vote per item.

    Args:
        item_rows (pandas.DataFrame): Rows for a single ``agenda_item_id`` (canonical fields).

    Returns:
        pandas.DataFrame: The subset representing the item's outcome vote.
    """
    main = item_rows[item_rows["motion"].map(_is_main_motion)]
    if not main.empty:
        return main
    if "motion" in item_rows and item_rows["motion"].notna().any():
        last_motion = item_rows["motion"].iloc[-1]
        return item_rows[item_rows["motion"] == last_motion]
    return item_rows


def _member_name(record: dict) -> str:
    """Resolve a full member name from either a combined or split-name CSV.

    Args:
        record (dict): A canonical-field row (may carry ``member`` or ``first_name``/``last_name``).

    Returns:
        str: The full member name (``""`` if none present).
    """
    member = str(record.get("member", "") or "").strip()
    if member:
        return member
    first = str(record.get("first_name", "") or "").strip()
    last = str(record.get("last_name", "") or "").strip()
    return f"{first} {last}".strip()


def _member_id(record: dict) -> str:
    """Resolve a normalized councillor id, preferring the surname when split out.

    Args:
        record (dict): A canonical-field row.

    Returns:
        str: The normalized councillor id slug.
    """
    last = str(record.get("last_name", "") or "").strip()
    return normalize_councillor_id(last) if last else normalize_councillor_id(_member_name(record))


def _to_votes_schema(canon: pd.DataFrame, source: str) -> pd.DataFrame:
    """Map canonical-field rows to the component's votes parquet schema (Yes/No only).

    Args:
        canon (pandas.DataFrame): Rows with the canonical fields.
        source (str): Provenance tag (``official_csv`` or ``mirror``).

    Returns:
        pandas.DataFrame: The votes-schema table, with Absent/recused rows dropped.
    """
    rows: list[dict] = []
    for record in canon.to_dict("records"):
        vote = str(record.get("vote", "") or "").strip()
        if vote.lower() not in _DIRECTIONAL_VOTES:
            continue  # drop Absent / Absent(Interest Declared) / blank
        member = _member_name(record)
        if not member:
            continue
        item_id = str(record.get("agenda_item_id", "") or "").strip()
        rows.append(
            {
                "agenda_item_id": item_id,
                "application_id": None,  # filled by the crosswalk
                "councillor_id": _member_id(record),
                "member_name": member,
                "committee": _resolve_committee(record.get("committee", ""), item_id),
                "vote": vote.title(),
                "meeting_date": str(record.get("meeting_date", "") or "")[:10],
                "motion": str(record.get("motion", "") or "").strip(),
                "item_title": str(record.get("item_title", "") or "").strip(),
                "result": str(record.get("result", "") or "").strip(),
                "source": source,
            }
        )
    return pd.DataFrame(rows)


def parse_member_vote_csv(text: str) -> pd.DataFrame:
    """Parse a TMMIS Member Voting Record CSV into the canonical votes schema.

    Tolerant of the export's header variations and split (First/Last) names, drops Absent
    rows, normalizes councillor ids, resolves the committee, and selects each item's main
    disposition motion.

    Args:
        text (str): The raw CSV text from the report export.

    Returns:
        pandas.DataFrame: Columns ``agenda_item_id``, ``application_id`` (None),
        ``councillor_id``, ``member_name``, ``committee``, ``vote``, ``meeting_date``,
        ``motion``, ``item_title``, ``result``, ``source``.

    Raises:
        ValueError: If the CSV has neither a member/name nor a vote column.
    """
    raw = pd.read_csv(io.StringIO(text))
    mapping = _map_columns(list(raw.columns))
    has_member = "member" in mapping or ("first_name" in mapping and "last_name" in mapping)
    if not has_member or "vote" not in mapping:
        raise ValueError(
            f"Member Voting Record CSV missing member/vote columns: {list(raw.columns)}"
        )

    canon = pd.DataFrame(
        {field: raw[mapping[field]] if field in mapping else "" for field in _CSV_HEADER_SYNONYMS}
    )
    canon["agenda_item_id"] = canon["agenda_item_id"].astype(str).str.strip()

    if canon["agenda_item_id"].ne("").any():
        parts = [select_main_motion_rows(grp) for _, grp in canon.groupby("agenda_item_id")]
        selected = pd.concat(parts, ignore_index=True) if parts else canon
    else:
        selected = canon
    return _to_votes_schema(selected, source="official_csv")


def load_member_vote_csv(path: str) -> pd.DataFrame:
    """Parse a downloaded Member Voting Record CSV file from disk.

    Args:
        path (str): Filesystem path to the CSV.

    Returns:
        pandas.DataFrame: The canonical votes-schema table.

    Raises:
        ValueError: If the CSV is missing required columns.
    """
    with open(path, encoding="utf-8-sig") as handle:
        return parse_member_vote_csv(handle.read())


def parse_mirror_item(html: str, item_id: str) -> pd.DataFrame:
    """Parse a torontoinsights mirror voting-record page into the votes schema.

    Args:
        html (str): The page HTML.
        item_id (str): The agenda item id the page is for (e.g. ``2025.EX22.4``).

    Returns:
        pandas.DataFrame: Votes-schema rows (source=``mirror``); empty if no roster is found.
    """
    text = re.sub(r"<[^>]+>", "\n", html)  # strip tags, keep text on its own lines
    rows: list[dict] = []
    current: str | None = None
    title_match = re.search(r"(20\d{2}\.[A-Z]{2}\d{1,3}\.\d{1,3})\s*[-–]\s*(.+)", text)
    item_title = title_match.group(2).strip() if title_match else ""
    for line in (line.strip() for line in text.splitlines() if line.strip()):
        header = re.match(r"(Yes|No)\s+Votes?\s*\(\d+\)", line, re.IGNORECASE)
        if header:
            current = header.group(1).title()
            continue
        name = re.sub(r"\s*\(ward.*$", "", line, flags=re.IGNORECASE).strip()
        if current and re.fullmatch(
            r"[A-Z][A-Za-zà-ÿ'’.\-]*(?:\s+[A-Z][A-Za-zà-ÿ'’.\-]*){1,3}", name
        ):
            rows.append(
                {
                    "agenda_item_id": item_id,
                    "application_id": None,
                    "councillor_id": normalize_councillor_id(name),
                    "member_name": name,
                    "committee": _committee_from_item_id(item_id),
                    "vote": current,
                    "meeting_date": "",
                    "motion": "Adopt the item",
                    "item_title": item_title,
                    "result": "",
                    "source": "mirror",
                }
            )
    return pd.DataFrame(rows)


def fetch_member_votes_playwright(
    term_id: str,
    decision_body_id: int = 0,
    from_date: str | None = None,
    to_date: str | None = None,
) -> pd.DataFrame:
    """Pull the official Member Voting Record CSV via a headless browser (Akamai-gated).

    Args:
        term_id (str): TMMIS council term id.
        decision_body_id (int): Committee/body id; ``0`` = full City Council.
        from_date (str | None): Inclusive ``YYYY-MM-DD`` lower bound.
        to_date (str | None): Inclusive ``YYYY-MM-DD`` upper bound.

    Returns:
        pandas.DataFrame: The canonical votes-schema table.

    Raises:
        ImportError: If Playwright is not installed.
        RuntimeError: If the export cannot be retrieved.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError("Playwright is required for the TMMIS CSV export.") from exc

    params = {
        "function": "getMemberVoteReport",
        "download": "csv",
        "termId": term_id,
        "decisionBodyId": str(decision_body_id),
    }
    if from_date:
        params["fromDate"] = from_date
    if to_date:
        params["toDate"] = to_date
    url = f"{config.TMMIS_MEMBER_VOTE_CSV}?{urlencode(params)}"

    with sync_playwright() as pw:  # pragma: no cover - network/browser dependent
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        response = page.goto(url, wait_until="networkidle")
        body = response.text() if response else page.content()
        browser.close()
    if not body or "," not in body.splitlines()[0]:
        raise RuntimeError("TMMIS export did not return CSV (Akamai block or bad params).")
    return parse_member_vote_csv(body)


def fetch_votes_mirror(item_ids: list[str]) -> pd.DataFrame:
    """Pull recorded votes for specific items from the non-Akamai mirror (seed labels).

    Args:
        item_ids (list[str]): Agenda item ids (e.g. ``["2025.EX22.4"]``).

    Returns:
        pandas.DataFrame: Concatenated votes-schema rows for the reachable items.

    Raises:
        httpx.HTTPError: If a mirror request hard-fails (per-item failures are skipped).
    """
    import httpx

    frames: list[pd.DataFrame] = []
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:  # pragma: no cover - network
        for item_id in item_ids:
            try:
                resp = client.get(f"{config.TMMIS_VOTE_MIRROR_BASE}/{item_id}/")
                if resp.status_code == 200:
                    frames.append(parse_mirror_item(resp.text, item_id))
            except httpx.HTTPError:
                continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
