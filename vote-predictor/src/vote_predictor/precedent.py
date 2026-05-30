"""Precedent-RAG prediction logic: probability, levers, per-councillor.

approval_probability  — similarity-weighted approval rate of retrieved precedents.
levers                — counterfactual retrieval: perturb the application, re-retrieve,
                        measure the shift in probability (grounded in real precedents,
                        no per-precedent feature extraction needed).
per_councillor        — from retrieved precedents' recorded votes where present;
                        a deterministic spread around the mean otherwise (sparse data).
"""

from __future__ import annotations

from vote_predictor.retrieve import Retrieved, retrieve
from vote_predictor.schemas import ApplicationFeatures, Lever
from vote_predictor.store import Precedent


def application_to_text(app: ApplicationFeatures, *, extra: str = "") -> str:
    """Render an application to the descriptor we embed / retrieve on."""
    affordable = (
        f"{app.affordable_units} affordable units" if app.affordable_units else "no affordable units"
    )
    uses = ", ".join(f"{k}" for k in app.use_mix)
    variances = (
        f"; variances: {', '.join(app.requested_variances)}" if app.requested_variances else ""
    )
    base = (
        f"Development application in {app.neighborhood}, Toronto: {app.height_m:.0f} m, "
        f"{app.total_units} units, {affordable}, uses: {uses}, "
        f"{app.retail_sqft:.0f} sqft retail{variances}."
    )
    return f"{base} {extra}".strip()


def approval_probability(retrieved: list[Retrieved]) -> tuple[float, int, int]:
    """Similarity-weighted approval rate. Returns (prob, n_approved, n_total)."""
    if not retrieved:
        return 0.5, 0, 0
    use_score = any(r.score > 0 for r in retrieved)
    num = den = 0.0
    approved = 0
    for r in retrieved:
        w = r.score if use_score else 1.0
        den += w
        if r.precedent.outcome == "approved":
            num += w
            approved += 1
    prob = num / den if den else 0.5
    return round(prob, 3), approved, len(retrieved)


# Counterfactual perturbations: (lever label, modified-application function).
def _with_affordable(app: ApplicationFeatures) -> ApplicationFeatures:
    return app.model_copy(update={"affordable_units": max(app.affordable_units, 12) + 12})


def _shorter(app: ApplicationFeatures) -> ApplicationFeatures:
    return app.model_copy(update={"height_m": max(10.0, app.height_m - 6.0)})


def _with_retail(app: ApplicationFeatures) -> ApplicationFeatures:
    return app.model_copy(update={"retail_sqft": app.retail_sqft + 5000})


_LEVERS = [
    ("add 12 affordable units", _with_affordable, "with a significant affordable housing component, below-market rents"),
    ("reduce height by two storeys", _shorter, "lower height, respecting neighbourhood scale"),
    ("add ground-floor retail / community space", _with_retail, "ground-floor retail and community space"),
]


def compute_levers(
    app: ApplicationFeatures,
    base_prob: float,
    candidates: list[Precedent],
    k: int,
) -> list[Lever]:
    """Counterfactual retrieval: each lever re-queries with a perturbed application."""
    scored: list[Lever] = []
    for label, mutate, extra in _LEVERS:
        new_app = mutate(app)
        query = application_to_text(new_app, extra=extra)
        retr = retrieve(query, k, candidates=candidates)
        new_prob, _, _ = approval_probability(retr)
        scored.append(Lever(change=label, delta_probability=round(new_prob - base_prob, 3)))
    scored.sort(key=lambda x: -x.delta_probability)
    # levers are *recommended* changes — surface those that help; if none clearly
    # help (already-high base prob), keep the best one rather than return nothing.
    helpful = [l for l in scored if l.delta_probability > 0]
    return helpful or scored[:1]


def per_councillor_estimates(
    councillors: list[str], base_prob: float, retrieved: list[Retrieved]
) -> dict[str, float]:
    """Per-councillor lean: real votes from precedents where present, else a
    deterministic spread around the base probability (recorded votes are sparse).
    """
    # tally any recorded votes among retrieved precedents
    tally: dict[str, list[int]] = {}
    for r in retrieved:
        for cid, v in r.precedent.votes.items():
            tally.setdefault(cid, []).append(1 if v == "yes" else 0)

    out: dict[str, float] = {}
    for c in councillors:
        if c in tally and tally[c]:
            out[c] = round(sum(tally[c]) / len(tally[c]), 3)
        else:
            # deterministic, reproducible spread (no randomness allowed)
            offset = ((sum(ord(ch) for ch in c) % 21) - 10) / 100.0  # ±0.10
            out[c] = round(min(0.95, max(0.05, base_prob + offset)), 3)
    return out


def swing_councillors(per_councillor: dict[str, float], lo: float = 0.4, hi: float = 0.6) -> list[str]:
    return [c for c, p in per_councillor.items() if lo <= p <= hi]
