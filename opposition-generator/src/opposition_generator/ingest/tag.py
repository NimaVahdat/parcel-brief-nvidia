"""LLM tagging pass over raw deputation text.

For each extracted letter, one LLM call pulls out the structured metadata the
retrieval/forecast pipeline relies on: neighborhood, canonical concern tags,
named organizing groups, and project type. Concerns are normalized to the fixed
taxonomy so they aggregate cleanly downstream.

Falls back to lightweight keyword tagging if the LLM is unavailable, so an ingest
run never stalls on a model outage.
"""

from __future__ import annotations

import re

from opposition_generator import config
from opposition_generator.forecast.taxonomy import CONCERN_ALIASES, normalize_concerns
from opposition_generator.llm import LLMError, chat_json

_PROJECT_TYPES = (
    "lowrise-residential",
    "midrise-residential",
    "midrise-mixed-use",
    "highrise-residential",
    "highrise-mixed-use",
    "other",
)

# crude org-name detector for the keyword fallback
_GROUP_RE = re.compile(
    r"\b([A-Z][\w&'-]+(?:\s+[A-Z][\w&'-]+){0,4}\s+"
    r"(?:Residents?\s+Association|Association|Network|BIA|Coalition|"
    r"Friends\s+of\s+[A-Z][\w-]+))",
)


def tag_deputation(
    text: str,
    *,
    fallback_neighborhood: str | None = None,
    context: str | None = None,
) -> dict:
    """Return {neighborhood, concerns[], groups[], project_type} for a letter.

    `context` is optional extra grounding (e.g. the agenda item title, which often
    contains the project address) to help neighborhood inference.
    """
    try:
        return _tag_with_llm(text, fallback_neighborhood, context)
    except LLMError:
        return _tag_with_keywords(text, fallback_neighborhood)


def _tag_with_llm(text: str, fallback_neighborhood: str | None, context: str | None) -> dict:
    system = (
        "You extract structured metadata from Toronto community deputation letters. "
        "Respond only with JSON."
    )
    ctx = f"Agenda item (for address/context): {context}\n\n" if context else ""
    prompt = (
        ctx
        + "From the deputation letter below, extract:\n"
        '- "neighborhood": the Toronto neighbourhood it concerns (best guess)\n'
        '- "concerns": list from [shadow, traffic, density, height, heritage, parking, '
        "affordability, displacement, construction, character, environment, privacy]\n"
        '- "groups": named residents associations / BIAs / coalitions mentioned\n'
        f'- "project_type": one of {list(_PROJECT_TYPES)}\n\n'
        'Respond as JSON: {"neighborhood": "...", "concerns": [...], '
        '"groups": [...], "project_type": "..."}\n\n'
        f"Letter:\n{text[:4000]}"
    )
    data = chat_json(prompt, system=system, temperature=0.1, model=config.TAG_MODEL)
    neighborhood = (data.get("neighborhood") or fallback_neighborhood or "").strip()
    project_type = data.get("project_type", "other")
    if project_type not in _PROJECT_TYPES:
        project_type = "other"
    return {
        "neighborhood": neighborhood,
        "concerns": normalize_concerns(data.get("concerns", [])),
        "groups": [g.strip() for g in data.get("groups", []) if g and g.strip()],
        "project_type": project_type,
    }


def _tag_with_keywords(text: str, fallback_neighborhood: str | None) -> dict:
    lower = text.lower()
    concerns = normalize_concerns(
        [alias for alias in CONCERN_ALIASES if alias in lower]
    )
    groups = sorted({m.group(1).strip() for m in _GROUP_RE.finditer(text)})
    return {
        "neighborhood": (fallback_neighborhood or "").strip(),
        "concerns": concerns,
        "groups": groups,
        "project_type": "other",
    }
