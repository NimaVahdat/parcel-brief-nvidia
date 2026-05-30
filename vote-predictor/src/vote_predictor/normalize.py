"""Small, dependency-free normalization helpers shared across the ingest sources.

Kept in its own module so the source modules (``tmmis_source``, ``crosswalk``) and the
contract adapter (``infer``) can all reuse them without importing each other.
"""

from __future__ import annotations

import re


def normalize_councillor_id(name: str) -> str:
    """Normalize a councillor name or id to a stable lowercase surname slug.

    Maps "Gord Perks", "Perks, Gord", and "perks" all to ``"perks"`` so the connector's
    placeholder ids and TMMIS member names reconcile to one key.

    Args:
        name (str): A councillor name or id in any of the observed formats.

    Returns:
        str: A lowercase surname slug with non-alphanumerics stripped.
    """
    cleaned = str(name).strip().lower()
    if "," in cleaned:  # "Perks, Gord" -> surname is the leading token
        cleaned = cleaned.split(",")[0]
    else:  # "Gord Perks" -> surname is the trailing token
        cleaned = cleaned.split()[-1] if cleaned.split() else cleaned
    return re.sub(r"[^a-z0-9]", "", cleaned)


#: Long street-type words -> the abbreviation the AIC datastore stores, so a TMMIS title
#: ("929 Queen Street East") and an AIC address ("929 QUEEN ST E") canonicalize to the same.
_STREET_TYPES = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "ROAD": "RD",
    "BOULEVARD": "BLVD",
    "DRIVE": "DR",
    "COURT": "CRT",
    "CRESCENT": "CRES",
    "PLACE": "PL",
    "LANE": "LN",
    "TERRACE": "TER",
    "SQUARE": "SQ",
    "PARKWAY": "PKWY",
    "TRAIL": "TRL",
    "GARDENS": "GDNS",
    "HEIGHTS": "HTS",
}
_DIRECTIONS = {
    "EAST": "E",
    "WEST": "W",
    "NORTH": "N",
    "SOUTH": "S",
    "NORTHEAST": "NE",
    "NORTHWEST": "NW",
    "SOUTHEAST": "SE",
    "SOUTHWEST": "SW",
}


def normalize_address(value: str | None) -> str:
    """Normalize a street address for fuzzy cross-system matching.

    Upper-cases, drops punctuation, and canonicalizes street-type and direction words to the
    abbreviations the AIC datastore uses, so an address parsed from a TMMIS item title
    compares cleanly to the AIC street components.

    Args:
        value (str | None): A raw address string.

    Returns:
        str: The normalized, canonicalized address (``""`` if empty).
    """
    if not value:
        return ""
    text = re.sub(r"[^\w\s]", " ", str(value).upper())
    tokens = [_STREET_TYPES.get(t, _DIRECTIONS.get(t, t)) for t in text.split()]
    return " ".join(tokens)
