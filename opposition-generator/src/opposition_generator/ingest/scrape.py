"""TMMIS deputation scraper.

TMMIS sits behind Akamai. Two facts from live reconnaissance shape this design:

  * The static PDFs under `www.toronto.ca/legdocs/...` are NOT Akamai-protected —
    they download fine over plain HTTP.
  * The dynamic site `secure.toronto.ca/council/` IS protected, and *headless*
    browsers get "Access Denied". A *headful* Chromium (real display) passes the
    bot check. So discovery needs a headful browser; downloading does not.

Discovery chain:
  1. /council/api/individual/meeting/{id}.json  -> agenda items (referenceNumber,
     nativeTermYear, statutoryReasonCd, title, wards). PLAN_ACT items are
     development applications.
  2. agenda-item.do?item={year}.{ref}  (server-rendered HTML) -> the
     legdocs/.../comm/communicationfile-<id>.pdf URLs for that item.
  3. httpx GET each PDF.

Run headful on the box's display, e.g.:  DISPLAY=:1 opposition-generator scrape
Requires the `scrape` extra (playwright + chromium).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from opposition_generator import config

RAW_DIR = config.DATA_DIR / "deputations" / "raw"
META_PATH = config.DATA_DIR / "deputations" / "scrape_meta.jsonl"
COUNCIL_ROOT = "https://secure.toronto.ca/council/"
MEETING_API = "https://secure.toronto.ca/council/api/individual/meeting/%d.json"
ITEM_PAGE = "https://secure.toronto.ca/council/agenda-item.do?item=%s"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
_REQUEST_DELAY_S = 0.8
_COMM_RE = re.compile(r"https?://[^\"']+/comm/communicationfile-\d+\.pdf")
# development applications: statutory planning items, or these title cues
_DEV_TITLE_RE = re.compile(
    r"zoning by-law|official plan amendment|committee of adjustment|"
    r"rezoning|site plan|draft plan of subdivision|consent application",
    re.I,
)


@dataclass
class CommDoc:
    deputation_id: str
    meeting_id: int
    committee: str
    agenda_item_ref: str
    agenda_item_title: str
    wards: str
    year: int
    source_url: str


def _is_development(item: dict) -> bool:
    if item.get("statutoryReasonCd") == "PLAN_ACT":
        return True
    return bool(_DEV_TITLE_RE.search(item.get("agendaItemTitle", "")))


def _committee_code(url: str) -> str:
    m = re.search(r"/legdocs/mmis/\d+/([a-z]+)/comm/", url)
    return m.group(1) if m else ""


def scrape_deputations(
    meeting_ids: list[int] | None = None,
    *,
    scan: tuple[int, int] | None = None,
    body_filter: tuple[str, ...] = ("Community Council",),
    headless: bool = False,
    max_files: int | None = None,
    dev_only: bool = True,
) -> list[Path]:
    """Scrape deputation PDFs for the given meeting ids.

    Walks each meeting's agenda items, keeps development applications, reads each
    item page for communication-file URLs, and downloads the PDFs. Writes a
    metadata sidecar (scrape_meta.jsonl) so ingest can attach item context.

    Pass explicit `meeting_ids`, or a `scan=(lo, hi)` meetingId range to discover
    meetings whose decision body matches `body_filter` within the same browser
    session.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Playwright required: pip install 'opposition-generator[scrape]' "
            "&& playwright install chromium"
        ) from exc

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    meta_fh = META_PATH.open("a", encoding="utf-8")
    http = httpx.Client(timeout=60, headers={"User-Agent": UA}, follow_redirects=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=UA, locale="en-CA", timezone_id="America/Toronto",
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()
        # prime Akamai cookies on the SPA root
        page.goto(COUNCIL_ROOT, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)

        if meeting_ids is None:
            if not scan:
                raise ValueError("provide meeting_ids or scan=(lo, hi)")
            meeting_ids = discover_meeting_ids(
                page, scan[0], scan[1], decision_body_contains=body_filter
            )

        for mid in meeting_ids:
            for doc in _meeting_comm_docs(page, mid, dev_only=dev_only):
                dest = RAW_DIR / f"{doc.year}-{doc.committee}-{doc.deputation_id}.pdf"
                if not dest.exists() and _download(http, doc.source_url, dest):
                    downloaded.append(dest)
                    meta_fh.write(json.dumps(asdict(doc), ensure_ascii=False) + "\n")
                    meta_fh.flush()
                time.sleep(_REQUEST_DELAY_S)
                if max_files and len(downloaded) >= max_files:
                    browser.close(); meta_fh.close(); http.close()
                    return downloaded
        browser.close()
    meta_fh.close(); http.close()
    return downloaded


def _meeting_comm_docs(page, meeting_id: int, *, dev_only: bool) -> list[CommDoc]:
    """Yield CommDoc for every communication PDF on a meeting's (dev) items."""
    try:
        rec = page.evaluate(
            "async (u) => { const r = await fetch(u); if(!r.ok) return null; return await r.json(); }",
            MEETING_API % meeting_id,
        )
    except Exception:
        return []
    if not rec:
        return []
    record = rec.get("Record", rec)
    sections = record.get("sections") or []
    docs: list[CommDoc] = []
    for section in sections:
        for item in section.get("agendaItems", []):
            if dev_only and not _is_development(item):
                continue
            year = item.get("nativeTermYear")
            ref = item.get("referenceNumber")
            if not (year and ref):
                continue
            for url in _item_comm_urls(page, f"{year}.{ref}"):
                docs.append(
                    CommDoc(
                        deputation_id=Path(url).stem,  # communicationfile-<id>
                        meeting_id=meeting_id,
                        committee=_committee_code(url),
                        agenda_item_ref=f"{year}.{ref}",
                        agenda_item_title=item.get("agendaItemTitle", ""),
                        wards=str(item.get("wards", "")),
                        year=int(year),
                        source_url=url,
                    )
                )
            time.sleep(_REQUEST_DELAY_S)
    return docs


def _item_comm_urls(page, item_ref: str) -> list[str]:
    """Read an agenda-item page and extract its communication-file PDF URLs."""
    try:
        page.goto(ITEM_PAGE % item_ref, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)
        html = page.content()
    except Exception:
        return []
    return sorted(set(_COMM_RE.findall(html)))


def discover_meeting_ids(
    page, lo: int, hi: int, *, decision_body_contains: tuple[str, ...] = ("Community Council",)
) -> list[int]:
    """Scan a meetingId range, keeping meetings whose body matches a filter.

    meetingIds are sequential integers; recent ones are ~27000+. This lets us
    enumerate historical meetings without a documented list endpoint.
    """
    keep: list[int] = []
    for mid in range(lo, hi + 1):
        try:
            rec = page.evaluate(
                "async (u) => { const r = await fetch(u); if(!r.ok) return null; const j = await r.json(); "
                "return (j.Record&&j.Record.meeting)?j.Record.meeting:null; }",
                MEETING_API % mid,
            )
        except Exception:
            rec = None
        if rec:
            name = rec.get("decisionBodyName", "")
            if any(s in name for s in decision_body_contains):
                keep.append(mid)
        time.sleep(0.2)
    return keep
