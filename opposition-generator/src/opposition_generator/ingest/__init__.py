"""Ingest subpackage: scrape TMMIS -> extract text -> LLM-tag -> deputations.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

from opposition_generator import config
from opposition_generator.ingest.extract import extract_text
from opposition_generator.ingest.scrape import (
    META_PATH,
    RAW_DIR,
    discover_meeting_ids,
    scrape_deputations,
)
from opposition_generator.ingest.tag import tag_deputation

CORPUS_PATH = config.DATA_DIR / "deputations.jsonl"


def _load_meta() -> dict[str, dict]:
    """Load the scrape metadata sidecar keyed by deputation_id."""
    meta: dict[str, dict] = {}
    if META_PATH.exists():
        with META_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    meta[rec["deputation_id"]] = rec
    return meta


def ingest_corpus(raw_dir: Path | None = None, *, limit: int | None = None) -> int:
    """Extract + LLM-tag every downloaded PDF into data/deputations.jsonl.

    Uses the scrape metadata sidecar (committee, agenda item ref/title, wards) to
    enrich each record and to give the tagger address context for neighborhood
    inference. Returns the number of deputations written.
    """
    raw_dir = raw_dir or RAW_DIR
    config.ensure_data_dir()
    meta = _load_meta()
    pdfs = sorted(Path(raw_dir).glob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]

    written = 0
    with CORPUS_PATH.open("w", encoding="utf-8") as out:
        for pdf in pdfs:
            text = extract_text(pdf)
            if not text or len(text) < 80:
                continue  # skip empty / unextractable
            m = meta.get(pdf.stem, {})
            tags = tag_deputation(text, context=m.get("agenda_item_title"))
            if not tags.get("neighborhood"):
                continue  # neighborhood is required for retrieval filtering
            record = {
                "deputation_id": pdf.stem,
                "agenda_item_id": m.get("agenda_item_ref", ""),
                "committee": m.get("committee", ""),
                "meeting_date": "",
                "neighborhood": tags["neighborhood"],
                "text": text,
                "concerns": tags["concerns"],
                "groups": tags["groups"],
                "project_type": tags["project_type"],
                "source_pdf_path": str(pdf),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
    return written


__all__ = [
    "scrape_deputations",
    "discover_meeting_ids",
    "ingest_corpus",
    "extract_text",
    "tag_deputation",
]
