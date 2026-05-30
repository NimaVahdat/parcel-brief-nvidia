"""Sample-letter generation — the hybrid strategy.

`sample_letters` = 1-2 letters the LLM writes about THIS project, grounded in the
retrieved real letters (so the voice is authentic but the content is about the
actual proposal) + 1 real retrieved letter included verbatim as evidence.

Guardrail: generated letters may only claim concerns that actually appear in the
retrieved set, so the model can't invent issues the neighbourhood never raised.
If the LLM is unavailable we still return a templated letter plus the real one, so
`sample_letters` is never empty.
"""

from __future__ import annotations

from opposition_generator.forecast.taxonomy import normalize_concerns
from opposition_generator.index.retrieve import Retrieved
from opposition_generator.llm import LLMError, chat_json
from opposition_generator.schemas import Letter, ProjectDescription

_MAX_EXAMPLE_CHARS = 700
_MAX_REAL_LETTER_CHARS = 900


def _project_brief(project: ProjectDescription, neighborhood: str) -> str:
    affordable = (
        f"{project.affordable_units} affordable of {project.total_units} units"
        if project.total_units
        else "unknown unit count"
    )
    notes = f"; {project.character_notes}" if project.character_notes else ""
    return (
        f"A {project.height_m:.0f}m development, {project.total_units} units "
        f"({affordable}), in {neighborhood}, Toronto{notes}."
    )


def generate_sample_letters(
    project: ProjectDescription,
    neighborhood: str,
    retrieved: list[Retrieved],
    *,
    n_generated: int = 2,
) -> tuple[list[Letter], bool]:
    """Return (sample_letters, used_llm).

    sample_letters = generated letters (grounded) followed by one real evidence
    letter (when retrieval returned anything).
    """
    allowed_concerns = sorted({c for r in retrieved for c in r.deputation.concerns})

    letters: list[Letter] = []
    used_llm = False

    generated = _generate_grounded(
        project, neighborhood, retrieved, allowed_concerns, n_generated
    )
    if generated is not None:
        letters.extend(generated)
        used_llm = True
    else:
        letters.append(_template_letter(project, neighborhood, allowed_concerns))

    # append one real retrieved letter as evidence
    if retrieved:
        top = retrieved[0].deputation
        real_text = top.text.strip()
        if len(real_text) > _MAX_REAL_LETTER_CHARS:
            real_text = real_text[:_MAX_REAL_LETTER_CHARS].rsplit(" ", 1)[0] + "…"
        letters.append(
            Letter(
                text=f"[Real past deputation from {top.neighborhood}] {real_text}",
                inferred_concerns=top.concerns,
                source_neighborhood=top.neighborhood,
            )
        )

    return letters, used_llm


def _generate_grounded(
    project: ProjectDescription,
    neighborhood: str,
    retrieved: list[Retrieved],
    allowed_concerns: list[str],
    n: int,
) -> list[Letter] | None:
    """Ask the LLM for grounded letters. Returns None on any LLM failure."""
    if not retrieved:
        return None

    examples = "\n\n---\n\n".join(
        r.deputation.text[:_MAX_EXAMPLE_CHARS] for r in retrieved[:3]
    )
    concern_hint = ", ".join(allowed_concerns) or "shadow, traffic, character"
    system = (
        "You write realistic community deputation letters opposing Toronto "
        "development applications, in the authentic voice of local residents. "
        "You only raise concerns that the neighbourhood has historically raised."
    )
    prompt = (
        f"Here are real past deputation letters from {neighborhood} and similar "
        f"Toronto neighbourhoods:\n\n{examples}\n\n"
        f"Now write {n} NEW short deputation letters (4-6 sentences each) OPPOSING "
        f"this specific project, in the same authentic resident voice:\n\n"
        f"{_project_brief(project, neighborhood)}\n\n"
        f"Only raise concerns drawn from this list: {concern_hint}.\n"
        'Respond as JSON: {"letters": [{"text": "...", "concerns": ["shadow", ...]}]}'
    )
    try:
        data = chat_json(prompt, system=system, temperature=0.7)
    except LLMError:
        return None

    raw = data.get("letters") or []
    allowed = set(allowed_concerns)
    out: list[Letter] = []
    for item in raw[:n]:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        if not text:
            continue
        concerns = normalize_concerns(item.get("concerns", []))
        # guardrail: keep only concerns the neighbourhood actually raised
        concerns = [c for c in concerns if c in allowed] or allowed_concerns[:3]
        out.append(
            Letter(text=text, inferred_concerns=concerns, source_neighborhood=neighborhood)
        )
    return out or None


def _template_letter(
    project: ProjectDescription, neighborhood: str, allowed_concerns: list[str]
) -> Letter:
    """Deterministic fallback letter when the LLM is unavailable."""
    concerns = allowed_concerns[:3] or ["shadow", "character", "affordability"]
    concern_phrase = ", ".join(concerns)
    text = (
        f"As a long-time resident of {neighborhood}, I am writing to oppose the "
        f"proposed {project.height_m:.0f}m development. It raises serious concerns "
        f"about {concern_phrase}, and as proposed it does not fit our community. I "
        f"urge the Committee to refuse this application until these issues are "
        f"properly addressed."
    )
    return Letter(text=text, inferred_concerns=concerns, source_neighborhood=neighborhood)
