"""Scrape past Toronto planning applications + outcomes from TMMIS.

Reuses the council JSON API discovered for opposition-generator. API-only (no PDF
parsing), so it is fast: meeting -> agenda items -> keep PLAN_ACT items -> derive the
outcome (approved/refused) from the decision-report title + item status.

TMMIS is Akamai-protected; run with a real display so the headful browser passes:
    DISPLAY=:1 vote-predictor scrape --meeting-lo 27000 --meeting-hi 27210

Writes data/precedents.jsonl. The embedded `text` strips outcome/recommendation
words so retrieval matches on the project, not the label.
"""

from __future__ import annotations

import json
import re
import time

from vote_predictor import config

COUNCIL_ROOT = "https://secure.toronto.ca/council/"
MEETING_API = "https://secure.toronto.ca/council/api/individual/meeting/%d.json"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")
CORPUS_PATH = config.DATA_DIR / "precedents.jsonl"

# segments to drop from the title so the embedded text carries no label
_DROP_RE = re.compile(
    r"approval|refus|decision report|final report|request for direction|"
    r"status report|recommendation|directions report|supplementary|report$", re.I)
_APP_TYPE_RE = re.compile(
    r"zoning by-law amendment|official plan amendment|committee of adjustment|"
    r"site plan|plan of subdivision|consent", re.I)


def _outcome(title: str, status: str) -> str | None:
    """Outcome class from title + council item status.

    Toronto approves nearly every planning item that reaches a decision, so the
    real two-class signal is *clean approval* vs *council-imposed amendments*:
      - refused (rare)            -> "refused"
      - AMENDED (approved w/ changes, i.e. contested) -> "amended"
      - ADOPTED / WO_RECS (approved as proposed)      -> "approved"
    `approval_probability` is then P(approved as proposed). POSTPONE/deferrals are
    skipped (no decision yet).
    """
    if "refus" in title.lower():
        return "refused"
    if status == "AMENDED":
        return "amended"
    if status in ("ADOPTED", "WO_RECS", "CARRIED"):
        return "approved"
    return None


def _app_type(title: str) -> str:
    m = _APP_TYPE_RE.search(title)
    return m.group(0).title() if m else ""


def _clean_text(title: str, ward: str) -> str:
    segs = [s.strip() for s in title.split(" - ")]
    kept = [s for s in segs if s and not _DROP_RE.search(s)]
    base = " - ".join(kept) if kept else segs[0]
    ward_part = f" (Ward {ward})" if ward else ""
    return f"Development application: {base}{ward_part}."


def scrape(
    meeting_ids: list[int] | None = None,
    *,
    scan: tuple[int, int] | None = None,
    body_filter: tuple[str, ...] = ("Community Council", "Planning and Housing"),
    headless: bool = False,
    max_items: int | None = None,
) -> int:
    """Scrape planning precedents; append to precedents.jsonl. Returns count written."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Playwright required: pip install playwright && playwright install chromium"
        ) from exc

    config.ensure_data_dir()
    written = 0
    seen_ids: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=UA, locale="en-CA", timezone_id="America/Toronto",
            viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.goto(COUNCIL_ROOT, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)

        if meeting_ids is None:
            if not scan:
                raise ValueError("provide meeting_ids or scan=(lo, hi)")
            meeting_ids = _discover(page, scan[0], scan[1], body_filter)

        with CORPUS_PATH.open("a", encoding="utf-8") as out:
            for mid in meeting_ids:
                for rec in _meeting_precedents(page, mid, seen_ids):
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out.flush()
                    written += 1
                    if max_items and written >= max_items:
                        browser.close()
                        return written
        browser.close()
    return written


def _discover(page, lo, hi, body_filter):
    keep = []
    for mid in range(lo, hi + 1):
        try:
            name = page.evaluate(
                "async (u)=>{const r=await fetch(u); if(!r.ok) return null; const j=await r.json();"
                "const m=j.Record&&j.Record.meeting; return (m&&m.decisionBody)?m.decisionBody.decisionBodyName:null;}",
                MEETING_API % mid)
        except Exception:
            name = None
        if name and any(s in name for s in body_filter):
            keep.append(mid)
        time.sleep(0.15)
    return keep


def _meeting_precedents(page, meeting_id, seen_ids):
    try:
        rec = page.evaluate(
            "async (u)=>{const r=await fetch(u); if(!r.ok) return null; return await r.json();}",
            MEETING_API % meeting_id)
    except Exception:
        return []
    if not rec:
        return []
    out = []
    for section in (rec.get("Record", rec).get("sections") or []):
        for item in section.get("agendaItems", []):
            if item.get("statutoryReasonCd") != "PLAN_ACT":
                continue
            title = item.get("agendaItemTitle", "")
            outcome = _outcome(title, item.get("itemStatusCd", ""))
            ref = item.get("referenceNumber")
            if not outcome or not ref:
                continue
            pid = f"{item.get('nativeTermYear')}.{ref}"
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            ward = str(item.get("wards", ""))
            out.append({
                "precedent_id": pid,
                "text": _clean_text(title, ward),
                "outcome": outcome,
                "ward": ward,
                "committee": "",
                "year": int(item.get("nativeTermYear") or 0),
                "app_type": _app_type(title),
                "address": title.split(" - ")[0].strip(),
                "votes": {},
            })
    return out
