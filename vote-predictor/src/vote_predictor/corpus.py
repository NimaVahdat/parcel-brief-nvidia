"""Load the precedent corpus (scraped jsonl, or the committed synthetic seed)."""

from __future__ import annotations

import json

from vote_predictor import config
from vote_predictor.seeds import SAMPLE_PRECEDENTS

CORPUS_PATH = config.DATA_DIR / "precedents.jsonl"
REQUIRED = ("precedent_id", "text", "outcome")


def _clean(r: dict) -> dict:
    return {
        "precedent_id": r["precedent_id"],
        "text": r["text"],
        "outcome": r["outcome"],
        "ward": r.get("ward", ""),
        "committee": r.get("committee", ""),
        "year": int(r.get("year", 0) or 0),
        "app_type": r.get("app_type", ""),
        "address": r.get("address", ""),
        "votes": r.get("votes", {}),
    }


def load_corpus(*, use_seed_if_missing: bool = True) -> list[dict]:
    if CORPUS_PATH.exists():
        rows: list[dict] = []
        with CORPUS_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                if all(raw.get(k) for k in REQUIRED):
                    rows.append(_clean(raw))
        if rows:
            return rows
    return [_clean(r) for r in SAMPLE_PRECEDENTS] if use_seed_if_missing else []


def load_seed() -> list[dict]:
    return [_clean(r) for r in SAMPLE_PRECEDENTS]
