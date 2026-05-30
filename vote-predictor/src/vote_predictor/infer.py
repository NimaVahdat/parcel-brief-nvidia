"""predict() — THE CONTRACT.

Precedent-RAG: retrieve similar past Toronto applications with known outcomes and
predict from them. Degrades gracefully (rag -> heuristic) and never raises, so the
connector pipeline stays alive.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from vote_predictor.precedent import (
    application_to_text,
    approval_probability,
    compute_levers,
    per_councillor_estimates,
    swing_councillors,
)
from vote_predictor.schemas import ApplicationFeatures, Lever, VotePrediction

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    prediction: VotePrediction
    mode: str            # "rag" | "heuristic"
    retrieved: int
    approved_of_retrieved: int


def predict_with_meta(
    application: ApplicationFeatures, councillors: list[str]
) -> PredictionResult:
    from vote_predictor import config
    from vote_predictor.retrieve import retrieve
    from vote_predictor.store import get_store

    try:
        candidates = get_store().fetch()
        retrieved = retrieve(application_to_text(application), config.DEFAULT_TOP_K,
                             candidates=candidates)
    except Exception as exc:  # store/embeddings unavailable
        logger.warning("retrieval failed (%s); heuristic fallback", exc)
        return PredictionResult(_heuristic(application, councillors), "heuristic", 0, 0)

    if not retrieved:
        return PredictionResult(_heuristic(application, councillors), "heuristic", 0, 0)

    base_prob, approved, total = approval_probability(retrieved)
    levers = compute_levers(application, base_prob, candidates, config.DEFAULT_TOP_K)
    per_c = per_councillor_estimates(councillors, base_prob, retrieved)
    pred = VotePrediction(
        approval_probability=base_prob,
        per_councillor=per_c,
        swing_councillors=swing_councillors(per_c),
        levers=levers,
    )
    return PredictionResult(pred, "rag", total, approved)


def predict(application: ApplicationFeatures, councillors: list[str]) -> VotePrediction:
    """Predict how Toronto council will vote. Always returns a valid VotePrediction."""
    try:
        return predict_with_meta(application, councillors).prediction
    except Exception as exc:  # absolute backstop
        logger.error("predict() failed (%s); heuristic", exc)
        return _heuristic(application, councillors)


def _heuristic(application: ApplicationFeatures, councillors: list[str]) -> VotePrediction:
    """Fallback when no corpus/embeddings are available."""
    p = 0.55
    if application.affordable_units >= 12:
        p += 0.18
    if application.height_m > 40:
        p -= 0.12
    if application.requested_variances:
        p -= 0.05 * min(len(application.requested_variances), 3)
    p = max(0.05, min(0.95, p))
    per_c = {
        c: round(min(0.95, max(0.05, p + ((sum(ord(x) for x in c) % 21) - 10) / 100.0)), 3)
        for c in councillors
    }
    return VotePrediction(
        approval_probability=round(p, 3),
        per_councillor=per_c,
        swing_councillors=[c for c, v in per_c.items() if 0.4 <= v <= 0.6],
        levers=[
            Lever(change="add 12 affordable units", delta_probability=0.16),
            Lever(change="reduce height by two storeys", delta_probability=0.06),
            Lever(change="add ground-floor retail / community space", delta_probability=0.05),
        ],
    )
