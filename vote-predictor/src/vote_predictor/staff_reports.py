"""Staff reports: the City Planning recommendation — the single strongest vote predictor.

Staff report PDFs live in the plain-HTTP (non-Akamai) legdocs tree and carry two things the
predictor needs: the recommendation (approve / approve-with-conditions / refuse) and the
"Planning Application Number" that bridges the report back to the CKAN AIC record.

The classifier is **title-first** by design. The Phase-0 adversarial pass showed that
substring-scanning the whole document mislabels real reports: the word "conditions" appears
in boilerplate (downgrading a clean Approval), and "refuse" fires on OLT-appeal boilerplate
("should Council refuse... the applicant may appeal"). So the disposition is read from the
report title ("Decision Report – Approval/Refusal") first, with the RECOMMENDATIONS block
used only to disambiguate, and standard Section 37/holding-symbol clauses do **not** downgrade
an approval (they are part of a normal rezoning approval, not a conditional one).
"""

from __future__ import annotations

import re

from vote_predictor import config
from vote_predictor.ckan_source import normalize_application_number

#: Title fragments that classify the report stage. Preliminary reports predate the
#: recommendation and must not be classified as a verdict.
_REPORT_TYPE_PATTERNS = [
    ("preliminary", re.compile(r"preliminary report", re.IGNORECASE)),
    ("decision", re.compile(r"decision report", re.IGNORECASE)),
    ("final", re.compile(r"final report", re.IGNORECASE)),
    ("supplementary", re.compile(r"supplementary report", re.IGNORECASE)),
]

#: Explicit conditional-approval language (NOT Section 37/holding, which are normal).
_CONDITIONAL_PATTERNS = [
    "with conditions",
    "subject to the conditions",
    "conditional approval",
    "approval subject to",
    "approve, subject to",
    "be approved subject to",
]

_APPLICATION_NUMBER_RE = re.compile(config.APPLICATION_NUMBER_RE)


def extract_text(pdf_bytes: bytes) -> str:
    """Extract selectable text from a staff-report PDF.

    Args:
        pdf_bytes (bytes): The raw PDF content.

    Returns:
        str: Concatenated page text (empty string if the PDF is image-only / unparseable).

    Raises:
        ImportError: If ``pypdf`` is not installed.
    """
    import io

    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:  # noqa: BLE001 - any malformed/image-only PDF yields no text
        return ""


def extract_title(text: str) -> str:
    """Heuristically recover the report title line from the report text.

    Args:
        text (str): Extracted report text.

    Returns:
        str: The best-guess title line (the first "... Report ..." line near the top), or "".
    """
    for line in (line.strip() for line in text.splitlines()[:40] if line.strip()):
        if re.search(r"\breport\b", line, re.IGNORECASE) and len(line) <= 160:
            return line
    return ""


def parse_report_type(title: str) -> str:
    """Classify the report stage from its title.

    Args:
        title (str): The report title line.

    Returns:
        str: ``preliminary`` | ``decision`` | ``final`` | ``supplementary`` | ``unknown``.
    """
    for label, pattern in _REPORT_TYPE_PATTERNS:
        if pattern.search(title or ""):
            return label
    return "unknown"


def extract_recommendations_block(text: str) -> str:
    """Slice out the RECOMMENDATIONS section (where the verdict actually lives).

    Args:
        text (str): Extracted report text.

    Returns:
        str: The recommendations block (up to ~2000 chars), or the sentence around the first
        "recommends that" lead, or "" if neither is present.
    """
    heading = re.search(r"\bRECOMMENDATIONS?\b", text)
    if heading:
        return text[heading.start() : heading.start() + 2000]
    lead = re.search(r"recommends?\s+that", text, re.IGNORECASE)
    if lead:
        return text[max(0, lead.start() - 80) : lead.start() + 600]
    return ""


def _approve_or_conditions(scope: str) -> str:
    """Decide approve vs approve_with_conditions from explicit conditional language only.

    Args:
        scope (str): The title or recommendations text to inspect.

    Returns:
        str: ``approve_with_conditions`` if explicit conditional approval language is present,
        else ``approve``. Section 37/holding symbols intentionally do NOT downgrade.
    """
    lowered = (scope or "").lower()
    if any(pattern in lowered for pattern in _CONDITIONAL_PATTERNS):
        return "approve_with_conditions"
    return "approve"


def classify_recommendation(title: str, body: str) -> str:
    """Classify the City Planning recommendation, title-first.

    Args:
        title (str): The report title line (the highest-precision signal).
        body (str): The report text (used only for the recommendations block).

    Returns:
        str: A key in ``config.STAFF_SIGNAL_MAP`` — ``approve`` | ``approve_with_conditions``
        | ``refuse`` | ``unknown``.
    """
    title_lower = (title or "").lower()
    if "preliminary report" in title_lower:
        return "unknown"  # predates the recommendation; do not invent a verdict
    if "refusal" in title_lower or re.search(r"[-–]\s*refus", title_lower):
        return "refuse"
    if "approval" in title_lower or re.search(r"[-–]\s*approv", title_lower):
        return _approve_or_conditions(extract_recommendations_block(body) or title)

    # No verdict in the title: read the RECOMMENDATIONS lead, scoped tightly so OLT-appeal
    # boilerplate ("should Council refuse ... may appeal") does not fire the refuse rule.
    rec = extract_recommendations_block(body)
    rec_lower = rec.lower()
    if not rec_lower:
        return "unknown"
    if re.search(r"recommends?\b[^.]{0,80}\brefus", rec_lower) or "not be approved" in rec_lower:
        return "refuse"
    if re.search(r"recommends?\b[^.]{0,80}\b(approv|amend|adopt|enact)", rec_lower):
        return _approve_or_conditions(rec)
    return "unknown"


def extract_application_number(text: str) -> str | None:
    """Extract and normalize the "Planning Application Number" from report text.

    Args:
        text (str): Extracted report text.

    Returns:
        str | None: The normalized ``APPLICATION#`` (the bridge to the AIC record), or None.
    """
    match = _APPLICATION_NUMBER_RE.search(text or "")
    return normalize_application_number(match.group(0)) if match else None


def parse_staff_report(
    pdf_bytes: bytes, report_uri: str, agenda_item_id: str | None = None
) -> dict | None:
    """Parse a staff-report PDF into a staff_recs row.

    Skips Preliminary reports (they carry no verdict). Returns None when the PDF has no
    extractable text (image-only — abstain rather than emit a false ``unknown``).

    Args:
        pdf_bytes (bytes): The raw PDF content.
        report_uri (str): The URL the PDF was fetched from (stored for the UI/trace).
        agenda_item_id (str | None): The TMMIS item id, if known from the agenda crawl.

    Returns:
        dict | None: A staff_recs row (``application_id``, ``parcel_id``, ``agenda_item_id``,
        ``recommendation``, ``report_uri``, ``report_type``), or None if unparseable/preliminary.
    """
    text = extract_text(pdf_bytes)
    if not text.strip():
        return None  # image-only PDF; OCR is out of scope (abstain)
    title = extract_title(text)
    report_type = parse_report_type(title)
    if report_type == "preliminary":
        return None
    application_id = extract_application_number(text)
    return {
        "application_id": application_id or "",
        "parcel_id": application_id or "",
        "agenda_item_id": agenda_item_id,
        "recommendation": classify_recommendation(title, text),
        "report_uri": report_uri,
        "report_type": report_type,
        "report_title": title,
    }


def fetch_report_pdf(url: str) -> bytes:
    """Fetch a staff-report PDF over plain HTTP (the legdocs tree is not Akamai-gated).

    Args:
        url (str): The ``backgroundfile-<id>.pdf`` URL.

    Returns:
        bytes: The PDF content.

    Raises:
        httpx.HTTPError: If the request fails.
    """
    import httpx

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:  # pragma: no cover - network
        response = client.get(url)
        response.raise_for_status()
        return response.content
