"""Load the deputation corpus from disk, or fall back to the committed seed.

The scraper writes data/deputations.jsonl (gitignored). When that file is absent
(fresh checkout, no scrape yet), `load_corpus()` returns the synthetic seed so the
rest of the pipeline still runs.
"""

from __future__ import annotations

import json

from opposition_generator import config
from opposition_generator.forecast.taxonomy import normalize_concerns
from opposition_generator.seeds.sample_deputations import SAMPLE_DEPUTATIONS

CORPUS_PATH = config.DATA_DIR / "deputations.jsonl"

REQUIRED_FIELDS = ("deputation_id", "neighborhood", "text")


def _clean(record: dict) -> dict:
    """Normalize a raw record: canonical concern keys, default optional fields."""
    return {
        "deputation_id": record["deputation_id"],
        "agenda_item_id": record.get("agenda_item_id", ""),
        "committee": record.get("committee", ""),
        "meeting_date": record.get("meeting_date", ""),
        "neighborhood": record["neighborhood"],
        "text": record["text"],
        "concerns": normalize_concerns(record.get("concerns", [])),
        "groups": record.get("groups", []),
        "project_type": record.get("project_type", ""),
        "source_pdf_path": record.get("source_pdf_path", ""),
    }


def load_corpus(*, use_seed_if_missing: bool = True) -> list[dict]:
    """Return the deputation corpus as a list of cleaned records.

    Reads data/deputations.jsonl if present; otherwise returns the seed corpus.
    """
    if CORPUS_PATH.exists():
        records: list[dict] = []
        with CORPUS_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                if all(raw.get(f) for f in REQUIRED_FIELDS):
                    records.append(_clean(raw))
        if records:
            return records

    if use_seed_if_missing:
        return [_clean(r) for r in SAMPLE_DEPUTATIONS]
    return []


def load_seed() -> list[dict]:
    """Return just the committed synthetic seed corpus."""
    return [_clean(r) for r in SAMPLE_DEPUTATIONS]
