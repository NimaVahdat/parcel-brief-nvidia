"""Ingest subpackage: scrape TMMIS -> extract text -> LLM-tag -> deputations.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

from opposition_generator import config
from opposition_generator.ingest.extract import extract_text
from opposition_generator.ingest.scrape import RAW_DIR, scrape_deputations
from opposition_generator.ingest.tag import tag_deputation

CORPUS_PATH = config.DATA_DIR / "deputations.jsonl"


def ingest_corpus(
    raw_dir: Path | None = None, *, limit: int | None = None
) -> int:
    """Extract + tag every downloaded PDF into data/deputations.jsonl.

    Returns the number of deputations written. Run scrape_deputations() first to
    populate the raw PDF directory.
    """
    raw_dir = raw_dir or RAW_DIR
    config.ensure_data_dir()
    pdfs = sorted(Path(raw_dir).glob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]

    written = 0
    with CORPUS_PATH.open("w", encoding="utf-8") as out:
        for pdf in pdfs:
            text = extract_text(pdf)
            if not text:
                continue
            meta = tag_deputation(text)
            if not meta.get("neighborhood"):
                continue  # neighborhood is required for retrieval filtering
            record = {
                "deputation_id": pdf.stem,
                "agenda_item_id": "",
                "committee": pdf.stem.split("-")[1] if "-" in pdf.stem else "",
                "meeting_date": "",
                "neighborhood": meta["neighborhood"],
                "text": text,
                "concerns": meta["concerns"],
                "groups": meta["groups"],
                "project_type": meta["project_type"],
                "source_pdf_path": str(pdf),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
    return written


__all__ = ["scrape_deputations", "ingest_corpus", "extract_text", "tag_deputation"]
