"""infer.py — THE CONTRACT. ``predict()`` is the only thing other components call.

Thin adapter over the agent: it normalizes councillor ids for grounding lookup, fetches the
staff recommendation internally (so Contract 1 stays unchanged), runs the panel, and re-keys
the result to the caller's original councillor ids.

``predict_with_trace`` is an *additive* sibling that also returns the per-councillor reasoning
trace (re-keyed to the caller's ids) for the service/UI. It does not change Contract 1.
"""

from __future__ import annotations

import functools

from vote_predictor.agent import VotePredictorAgent
from vote_predictor.ingest import fetch_staff_recommendation
from vote_predictor.normalize import normalize_councillor_id
from vote_predictor.schemas import AgentTrace, ApplicationFeatures, VotePrediction


@functools.lru_cache(maxsize=1)
def _agent() -> VotePredictorAgent:
    """Build the agent once and reuse it across predict() calls.

    Returns:
        VotePredictorAgent: The shared agent instance (profiles loaded once).
    """
    return VotePredictorAgent()


def _normalized_inputs(
    application: ApplicationFeatures, councillors: list[str]
) -> tuple[dict, dict[str, str], str, str | None]:
    """Resolve the shared inputs for both predict entry points.

    Args:
        application (ApplicationFeatures): The Contract-1 application.
        councillors (list[str]): The caller's councillor ids.

    Returns:
        tuple: ``(app_dict, norm_map, staff_rec, ward_norm)`` where ``norm_map`` maps each
        caller id to its normalized form.
    """
    app_dict = application.model_dump()
    staff_rec = fetch_staff_recommendation(app_dict.get("parcel_id", ""))
    ward_raw = app_dict.get("ward_councillor_id")
    ward_norm = normalize_councillor_id(ward_raw) if ward_raw else None
    norm_map = {c: normalize_councillor_id(c) for c in councillors}
    return app_dict, norm_map, staff_rec, ward_norm


def _rekey_prediction(
    prediction: VotePrediction, councillors: list[str], norm_map: dict[str, str]
) -> VotePrediction:
    """Re-key an agent prediction from normalized ids back to the caller's original ids.

    Args:
        prediction (VotePrediction): The agent prediction keyed by normalized councillor ids.
        councillors (list[str]): The caller's original councillor ids.
        norm_map (dict[str, str]): Caller id -> normalized id.

    Returns:
        VotePrediction: The same prediction keyed by the caller's original ids.
    """
    return VotePrediction(
        approval_probability=prediction.approval_probability,
        per_councillor={c: prediction.per_councillor[norm_map[c]] for c in councillors},
        swing_councillors=[c for c in councillors if norm_map[c] in prediction.swing_councillors],
        levers=prediction.levers,
    )


def predict(application: ApplicationFeatures, councillors: list[str]) -> VotePrediction:
    """Predict how council will vote on a development application.

    Args:
        application (ApplicationFeatures): Structured features of the proposed project.
        councillors (list[str]): Councillor ids serving on the relevant committee.

    Returns:
        VotePrediction: Approval probability, per-councillor Yes-probabilities (keyed by the
        caller's original councillor ids), swing councillors, and counterfactual levers.
    """
    app_dict, norm_map, staff_rec, ward_norm = _normalized_inputs(application, councillors)
    norm_ids = list(dict.fromkeys(norm_map.values()))  # dedup collided surnames
    prediction = _agent().predict(app_dict, norm_ids, staff_rec, ward_norm)
    return _rekey_prediction(prediction, councillors, norm_map)


def predict_with_trace(
    application: ApplicationFeatures, councillors: list[str]
) -> tuple[VotePrediction, AgentTrace]:
    """Predict and also return the per-councillor reasoning trace (additive; not Contract 1).

    Args:
        application (ApplicationFeatures): Structured features of the proposed project.
        councillors (list[str]): Councillor ids serving on the relevant committee.

    Returns:
        tuple[VotePrediction, AgentTrace]: The Contract-1 prediction (caller-keyed) and the
        reasoning trace with its councillor ids re-keyed to the caller's ids.
    """
    app_dict, norm_map, staff_rec, ward_norm = _normalized_inputs(application, councillors)
    norm_ids = list(dict.fromkeys(norm_map.values()))  # dedup collided surnames
    prediction, trace = _agent().predict_with_trace(app_dict, norm_ids, staff_rec, ward_norm)
    reverse: dict[str, str] = {}
    for original, norm in norm_map.items():
        reverse.setdefault(norm, original)

    rekeyed = [
        reasoning.model_copy(
            update={"councillor_id": reverse.get(reasoning.councillor_id, reasoning.councillor_id)}
        )
        for reasoning in trace.councillors
    ]
    out_prediction = _rekey_prediction(prediction, councillors, norm_map)
    return out_prediction, trace.model_copy(update={"councillors": rekeyed})
