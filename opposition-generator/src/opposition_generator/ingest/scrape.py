"""TMMIS deputation scraper (Playwright).

TMMIS sits behind Akamai and 403s plain server-side fetches (see docs/DATA.md), so
we drive a real headless browser. Deputations are attached to agenda items as
`legdocs/mmis/YYYY/<committee>/comm/communicationfile-<id>.pdf`.

This downloads the raw PDFs to data/deputations/raw/. Text extraction + tagging
happen in ingest_corpus() (see __init__.py) so scraping and parsing can run
independently. Selectors marked TODO should be verified against the live site
before a full multi-year run; the URL/path patterns are taken from docs/DATA.md.

Note: a full historical scrape is a large, outward-facing job against a City of
Toronto site — run it deliberately and politely (the default delay throttles
requests), not casually.
"""

from __future__ import annotations

import time
from pathlib import Path

from opposition_generator import config

RAW_DIR = config.DATA_DIR / "deputations" / "raw"
TMMIS_BASE = "https://www.toronto.ca/legdocs/mmis"
# Committee codes seen in TMMIS paths; extend as needed.
COMMITTEES = ("te", "ec", "ph", "cc", "ie", "gl", "ny", "sc", "ey")
_REQUEST_DELAY_S = 1.0


def scrape_deputations(
    start_year: int = 2014,
    end_year: int = 2026,
    committees: tuple[str, ...] = COMMITTEES,
    *,
    headless: bool = True,
    max_files: int | None = None,
) -> list[Path]:
    """Download communication-file PDFs from TMMIS committee agendas.

    Returns the list of downloaded PDF paths. Requires the `scrape` extra
    (`pip install 'opposition-generator[scrape]'` then `playwright install chromium`).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Playwright is required to scrape: pip install 'opposition-generator[scrape]' "
            "&& playwright install chromium"
        ) from exc

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            accept_downloads=True,
        )
        page = context.new_page()

        for year in range(start_year, end_year + 1):
            for committee in committees:
                comm_index = f"{TMMIS_BASE}/{year}/{committee}/comm/"
                try:
                    page.goto(comm_index, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    continue  # body/year/committee combo may not exist

                # TODO: verify selector against live DOM. The comm/ directory listing
                # links each communicationfile-*.pdf; an autoindex exposes <a href>.
                hrefs = page.eval_on_selector_all(
                    "a[href*='communicationfile-']",
                    "els => els.map(e => e.getAttribute('href'))",
                )
                for href in hrefs:
                    if not href or "communicationfile-" not in href:
                        continue
                    url = href if href.startswith("http") else comm_index + href.lstrip("/")
                    dest = RAW_DIR / f"{year}-{committee}-{Path(href).name}"
                    if dest.exists():
                        continue
                    if _download(page, url, dest):
                        downloaded.append(dest)
                    time.sleep(_REQUEST_DELAY_S)
                    if max_files and len(downloaded) >= max_files:
                        browser.close()
                        return downloaded

        browser.close()
    return downloaded


def _download(page, url: str, dest: Path) -> bool:
    """Fetch a PDF through the browser context (carries Akamai cookies)."""
    try:
        resp = page.request.get(url, timeout=30000)
        if resp.ok and "pdf" in resp.headers.get("content-type", "").lower():
            dest.write_bytes(resp.body())
            return True
    except Exception:
        pass
    return False
