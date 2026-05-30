"""PDF text extraction with an OCR fallback for scanned deputations.

Per docs/DATA.md most TMMIS deputations are text-extractable, but ~10-20% (older
items, handwritten letters, marked-up plans) are image-only and need OCR.

Strategy: try pypdf page-by-page; if a page yields no usable text, render it and
run pytesseract. Both libraries are optional extras — if they're missing we raise a
clear error rather than fail at import time.
"""

from __future__ import annotations

from pathlib import Path

_MIN_USABLE_CHARS = 20  # a page with fewer extracted chars is treated as a scan


def extract_text(pdf_path: str | Path) -> str:
    """Return the full text of a deputation PDF, OCR-ing pages with no text layer."""
    pdf_path = Path(pdf_path)
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pypdf is required for extraction: pip install 'opposition-generator[ocr]'"
        ) from exc

    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for page_no, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if len(text) < _MIN_USABLE_CHARS:
            text = _ocr_page(pdf_path, page_no).strip() or text
        if text:
            pages.append(text)
    return "\n\n".join(pages).strip()


def _ocr_page(pdf_path: Path, page_no: int) -> str:
    """OCR a single PDF page. Returns "" if OCR deps are unavailable."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        return ""
    try:
        images = convert_from_path(
            str(pdf_path), first_page=page_no + 1, last_page=page_no + 1, dpi=200
        )
    except Exception:
        return ""
    return "\n".join(pytesseract.image_to_string(img) for img in images)
