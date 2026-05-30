"""Controlled vocabulary for community concerns + their default mitigations.

A fixed concern taxonomy keeps `top_concerns` keys consistent across deputations
so they can be aggregated and compared. Free-text tags from the LLM ingest pass are
normalized into these canonical keys via CONCERN_ALIASES.
"""

from __future__ import annotations

# Canonical concern keys. Order is stable for deterministic output.
CONCERNS: tuple[str, ...] = (
    "shadow",
    "traffic",
    "density",
    "height",
    "heritage",
    "parking",
    "affordability",
    "displacement",
    "construction",
    "character",
    "environment",
    "privacy",
)

# Map common surface forms / synonyms onto the canonical concern keys.
CONCERN_ALIASES: dict[str, str] = {
    "shadow": "shadow",
    "shadowing": "shadow",
    "sun": "shadow",
    "sunlight": "shadow",
    "overshadowing": "shadow",
    "traffic": "traffic",
    "congestion": "traffic",
    "gridlock": "traffic",
    "density": "density",
    "overdevelopment": "density",
    "overcrowding": "density",
    "intensification": "density",
    "height": "height",
    "tall": "height",
    "massing": "height",
    "heritage": "heritage",
    "historic": "heritage",
    "conservation": "heritage",
    "parking": "parking",
    "loading": "parking",
    "affordability": "affordability",
    "affordable": "affordability",
    "rent": "affordability",
    "displacement": "displacement",
    "eviction": "displacement",
    "gentrification": "displacement",
    "renoviction": "displacement",
    "construction": "construction",
    "noise": "construction",
    "dust": "construction",
    "character": "character",
    "neighbourhood character": "character",
    "neighborhood character": "character",
    "fit": "character",
    "scale": "character",
    "environment": "environment",
    "trees": "environment",
    "canopy": "environment",
    "green": "environment",
    "stormwater": "environment",
    "privacy": "privacy",
    "overlook": "privacy",
    "wind": "privacy",
}

# Default mitigation per concern — phrased as an actionable project change.
CONCERN_MITIGATIONS: dict[str, str] = {
    "shadow": "step back upper storeys and run a sun/shadow study showing 5h sidewalk sunlight at the equinoxes",
    "traffic": "fund a transportation demand-management plan and reduce curb-cut conflicts",
    "density": "transfer some density to lower podium floors to ease the perceived bulk",
    "height": "reduce height at the street wall and transition down toward neighbouring low-rise",
    "heritage": "retain and integrate the heritage frontage rather than demolish",
    "parking": "meet or modestly exceed the parking/loading minimum and add secure bike parking",
    "affordability": "add affordable units (a 10-15% set-aside is historically associated with reduced opposition)",
    "displacement": "guarantee right-of-first-refusal and relocation support for existing tenants",
    "construction": "commit to a construction-management plan limiting noise, dust and haul-route hours",
    "character": "use brick/masonry and a mid-rise typology that matches the street's vernacular",
    "environment": "preserve mature trees on site and add green roof / stormwater retention",
    "privacy": "increase side setbacks and angle balconies away from adjacent rear yards",
}


def normalize_concern(raw: str) -> str | None:
    """Map a raw concern tag to a canonical key, or None if unrecognized."""
    key = raw.strip().lower()
    if key in CONCERN_ALIASES:
        return CONCERN_ALIASES[key]
    # substring fallback: "shadow impact" -> "shadow"
    for alias, canonical in CONCERN_ALIASES.items():
        if alias in key:
            return canonical
    return None


def normalize_concerns(raw_list: list[str]) -> list[str]:
    """Normalize + dedupe a list of raw concern tags into canonical keys."""
    seen: list[str] = []
    for raw in raw_list:
        c = normalize_concern(raw)
        if c and c not in seen:
            seen.append(c)
    return seen


def mitigation_for(concern: str) -> str:
    """Return the default mitigation phrase for a canonical concern key."""
    return CONCERN_MITIGATIONS.get(concern, f"address resident concerns about {concern}")


def canonical_group(name: str) -> str:
    """Light normalization of an organizing-group name for dedup/counting.

    Collapses whitespace and common suffixes so "Trinity Bellwoods Residents Assoc."
    and "Trinity-Bellwoods Residents Association" count as the same group.
    """
    n = " ".join(name.split())
    n = n.replace("Assoc.", "Association").replace("Assn", "Association")
    n = n.replace("Resident's", "Residents").replace("Residents'", "Residents")
    return n.strip(" .,")
