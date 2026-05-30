"""TMMIS deputation scraping + PDF text extraction.

Output target (./data/deputations.parquet):
- deputation_id (str)
- agenda_item_id (str)
- committee (str)
- meeting_date (date)
- neighborhood (str | None — best-effort from address parsing or agenda metadata)
- text (str — extracted from PDF, OCR fallback for scans)
- source_pdf_path (str)
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def scrape_deputations(start_year: int = 2014, end_year: int = 2026) -> None:
    """Scrape TMMIS communication-file PDFs from committee agendas.

    TODO: implement with Playwright. Iterate over committee meetings, find each
    agenda item that has communication files, download every PDF matching the
    pattern legdocs/mmis/YYYY/<committee>/comm/communicationfile-<id>.pdf.
    """
    raise NotImplementedError("Implement with Playwright; see docs/DATA.md")


def extract_text(pdf_path: Path) -> str:
    """Extract text from a deputation PDF. OCR fallback for scans.

    TODO: try pypdf first; if the page returns empty text, fall back to pytesseract.
    """
    raise NotImplementedError("Implement pypdf + pytesseract fallback")


if __name__ == "__main__":
    print("Not implemented yet.")
