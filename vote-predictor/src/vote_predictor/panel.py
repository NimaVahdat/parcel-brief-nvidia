"""The multi-agent panel: per-councillor Reasoner, deterministic Skeptic, and Clerk.

This is the core upgrade over the single grounded LLM call:

* **Reasoner** (LLM, nemotron-3-super) — reasons per councillor from that councillor's record,
  the staff recommendation, and retrieved precedent, emitting ``p_yes``, a one-line rationale,
  and the precedent ids it cited.
* **Skeptic** (deterministic gate) — adversarially audits each Reasoner claim against the
  actual record. A claim with no councillor history AND no valid cited precedent is
  **rejected and forced to abstain to the councillor's prior**; a claim that strays far from
  the councillor's record without precedent support is pulled back. Only grounded claims ship.
  Making the gate deterministic (not another LLM) is what makes "only grounded claims ship" a
  real mechanism and removes the silent ~0.62 fabrication the Phase-0 audit found.
* **Clerk** — the deterministic Poisson-binomial aggregation in ``aggregate.py`` (reused; the
  LLM never does the committee math).

When the model is unreachable the Reasoner degrades to a transparent record+staff heuristic so
the same Skeptic and trace still apply and nothing hard-fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vote_predictor import config, retrieval
from vote_predictor.aggregate import sigmoid
from vote_predictor.features import build_features
from vote_predictor.schemas import CouncillorReasoning, EvidenceRef

#: Reasoner-degraded heuristic weights — a transparent, grounded scorer (not a trained model)
#: used when the LLM endpoint is unavailable.
_FALLBACK_WEIGHTS = {
    "staff": 1.7,
    "ward": 0.9,
    "affordable": 1.3,
    "variance": -0.16,
    "height_over": -0.45,
}

_REASONER_SYSTEM = (
    "You are a panel of per-councillor analysts forecasting a Toronto council vote. Reason "
    "ONLY from the evidence block: a councillor's own voting record, the city planning staff "
    "recommendation, and the listed precedent applications. Cite precedent ids VERBATIM from "
    "the evidence in 'cites'. If a councillor has no recorded history AND no relevant "
    "precedent, do not invent confidence — leave 'cites' empty; an adversarial Skeptic audits "
    "every claim and will reject uncited or over-confident probabilities. Respond with STRICT "
    "JSON only."
)


@dataclass
class PanelOutput:
    """The panel's result for one prediction.

    Attributes:
        per_councillor (dict[str, float]): Shipped (post-Skeptic) Yes-probabilities.
        traces (list[CouncillorReasoning]): Per-councillor reasoning + Skeptic verdicts.
        mode (str): ``panel`` (LLM Reasoner) or ``fallback`` (deterministic Reasoner).
        precedent_ids (list[str]): Application ids retrieved as precedent.
    """

    per_councillor: dict[str, float]
    traces: list[CouncillorReasoning]
    mode: str
    precedent_ids: list[str] = field(default_factory=list)


def _clamp01(value: float) -> float:
    """Clamp a value into the [0, 1] probability range.

    Args:
        value (float): Any real number.

    Returns:
        float: The value clamped to [0, 1].
    """
    return float(min(max(value, 0.0), 1.0))


def _councillor_prior(profile: dict | None, global_logit: float) -> float:
    """Compute a councillor's prior Yes-probability from their profile (or the global prior).

    Args:
        profile (dict | None): The councillor's profile, if any.
        global_logit (float): Mean propensity logit across known councillors.

    Returns:
        float: The smoothed prior Yes-probability in (0, 1).
    """
    logit = profile.get("propensity_logit", global_logit) if profile else global_logit
    return _clamp01(sigmoid(logit))


def deterministic_claims(
    application: dict,
    councillors: list[str],
    profiles: dict[str, dict],
    staff_signal: float,
    ward: str | None,
    global_logit: float,
) -> dict[str, dict]:
    """Score each councillor with the transparent record+staff heuristic (degraded Reasoner).

    Args:
        application (dict): The application fields.
        councillors (list[str]): Normalized councillor ids.
        profiles (dict[str, dict]): Councillor profiles.
        staff_signal (float): Staff recommendation signal in [-1, 1].
        ward (str | None): Ward councillor id, if known.
        global_logit (float): Mean propensity logit (fallback base).

    Returns:
        dict[str, dict]: ``{cid: {"p_yes", "reason", "cites": []}}``.
    """
    feats = build_features(application)
    claims: dict[str, dict] = {}
    for cid in councillors:
        base = profiles.get(cid, {}).get("propensity_logit", global_logit)
        logit = (
            base
            + _FALLBACK_WEIGHTS["staff"] * staff_signal
            + _FALLBACK_WEIGHTS["ward"] * (1.0 if cid == ward else 0.0)
            + _FALLBACK_WEIGHTS["affordable"] * (feats.affordable_share - 0.1)
            + _FALLBACK_WEIGHTS["variance"] * feats.requested_variances_count
            + _FALLBACK_WEIGHTS["height_over"] * feats.height_over_ratio
        )
        claims[cid] = {
            "p_yes": _clamp01(sigmoid(logit)),
            "reason": "record + staff-signal heuristic (model offline)",
            "cites": [],
        }
    return claims


def _reasoner_messages(context: str, councillors: list[str]) -> list[dict]:
    """Build the Reasoner chat messages from the grounding context.

    Args:
        context (str): The grounding evidence block from ``retrieval.format_context``.
        councillors (list[str]): Normalized councillor ids that must appear in the output.

    Returns:
        list[dict]: OpenAI-style messages for the Reasoner call.
    """
    user = (
        f"{context}\n\n"
        f"For EVERY councillor in {councillors}, return JSON of this exact shape:\n"
        '{"per_councillor": {"<id>": {"p_yes": 0.0, "reason": "...", "cites": ["<precedent id>"]}}}\n'
        "p_yes is the probability (0-1) of a Yes vote. 'cites' lists precedent application ids "
        "from the evidence that informed the call (empty if none apply). Reason from the "
        "councillor's record and the staff recommendation first."
    )
    return [
        {"role": "system", "content": _REASONER_SYSTEM},
        {"role": "user", "content": user},
    ]


def run_reasoner_llm(context: str, councillors: list[str]) -> dict[str, dict]:
    """Run the LLM Reasoner and return per-councillor claims (or {} on any failure).

    Args:
        context (str): The grounding evidence block.
        councillors (list[str]): Normalized councillor ids.

    Returns:
        dict[str, dict]: ``{cid: {"p_yes", "reason", "cites"}}``; empty if the endpoint is
        unreachable or returns unusable output (the caller degrades to the heuristic).
    """
    from vote_predictor import llm_wrapper

    try:
        raw = llm_wrapper.chat_json(_reasoner_messages(context, councillors))
    except Exception:  # noqa: BLE001 - any failure degrades to the deterministic Reasoner
        return {}
    per = raw.get("per_councillor", {}) if isinstance(raw, dict) else {}
    return per if isinstance(per, dict) else {}


def skeptic_review(
    councillor_id: str,
    claim: dict,
    profile: dict | None,
    valid_precedent_ids: set[str],
    precedent_detail: dict[str, str],
    staff_rec: str,
    global_logit: float,
) -> CouncillorReasoning:
    """Adversarially audit one Reasoner claim; force an abstain when grounding is absent.

    The hard gate: a claim with neither a sufficient councillor record nor a valid cited
    precedent is rejected and the probability is replaced by the councillor's prior (basis
    becomes ``prior``, ``grounded`` is False). A claim that strays far from the councillor's
    record without precedent support is pulled back toward the record.

    Args:
        councillor_id (str): Normalized councillor id.
        claim (dict): The Reasoner claim ``{"p_yes", "reason", "cites"}``.
        profile (dict | None): The councillor's profile, if any.
        valid_precedent_ids (set[str]): Precedent ids actually present in the retrieved set.
        precedent_detail (dict[str, str]): Map of precedent id -> a short outcome description.
        staff_rec (str): The staff recommendation key (cited as evidence when non-unknown).
        global_logit (float): Mean propensity logit (fallback base for the prior).

    Returns:
        CouncillorReasoning: The shipped probability, basis, evidence, and Skeptic verdict.
    """
    prior = _councillor_prior(profile, global_logit)
    n_votes = int(profile.get("n_votes", 0)) if profile else 0
    has_record = n_votes >= config.MIN_GROUNDING_VOTES
    rationale = str(claim.get("reason", "") or "").strip()
    cites = claim.get("cites", []) if isinstance(claim.get("cites"), list) else []
    cited_precedents = [str(c) for c in cites if str(c) in valid_precedent_ids]
    p_yes = _clamp01(float(claim.get("p_yes", prior)))

    evidence: list[EvidenceRef] = []
    if has_record:
        evidence.append(
            EvidenceRef(
                kind="councillor_record",
                ref_id=councillor_id,
                detail=f"{n_votes} recorded votes, {profile.get('yes_rate', 0):.0%} Yes",
            )
        )
    for pid in cited_precedents:
        evidence.append(
            EvidenceRef(kind="precedent", ref_id=pid, detail=precedent_detail.get(pid, "precedent"))
        )
    if staff_rec and staff_rec != "unknown":
        evidence.append(EvidenceRef(kind="staff_rec", ref_id="staff", detail=f"staff: {staff_rec}"))

    # Gate 1: ungrounded -> abstain to prior. Distinguish a claim that cited nothing valid
    # (rejected_uncited) from one with no evidence available at all (forced_abstain).
    if not has_record and not cited_precedents:
        verdict = "rejected_uncited" if cites else "forced_abstain"
        note = (
            "cited no valid precedent and councillor has no usable record; abstained to prior"
            if cites
            else "no councillor record or precedent available; abstained to prior"
        )
        return CouncillorReasoning(
            councillor_id=councillor_id,
            p_yes=round(prior, 4),
            grounded=False,
            basis="prior",
            rationale=rationale or "no grounding",
            evidence=evidence,
            skeptic_verdict=verdict,
            skeptic_note=note,
            prior_p_yes=round(prior, 4),
        )

    # Gate 2: over-confident vs the councillor's own record without precedent -> pull back.
    if abs(p_yes - prior) > config.OVERCONFIDENCE_DELTA and not cited_precedents:
        pulled = round((p_yes + prior) / 2.0, 4)
        return CouncillorReasoning(
            councillor_id=councillor_id,
            p_yes=pulled,
            grounded=True,
            basis="record",
            rationale=rationale or "record-grounded",
            evidence=evidence,
            skeptic_verdict="downgraded_overconfident",
            skeptic_note=(
                f"claim {p_yes:.2f} strayed from record prior {prior:.2f} with no precedent; "
                "pulled toward the record"
            ),
            prior_p_yes=round(prior, 4),
        )

    basis = "precedent" if cited_precedents else "record"
    return CouncillorReasoning(
        councillor_id=councillor_id,
        p_yes=round(p_yes, 4),
        grounded=True,
        basis=basis,
        rationale=rationale or f"grounded in {basis}",
        evidence=evidence,
        skeptic_verdict="accepted",
        skeptic_note=f"claim grounded in {basis}",
        prior_p_yes=round(prior, 4),
    )


def run_panel(
    application: dict,
    councillors: list[str],
    profiles: dict[str, dict],
    staff_rec: str,
    staff_signal: float,
    similar: list[dict],
    ward: str | None,
    use_llm: bool,
) -> PanelOutput:
    """Run Reasoner -> Skeptic for every councillor and return shipped probabilities + trace.

    Args:
        application (dict): The application fields.
        councillors (list[str]): Normalized councillor ids.
        profiles (dict[str, dict]): Councillor profiles.
        staff_rec (str): Staff recommendation key.
        staff_signal (float): Staff signal in [-1, 1].
        similar (list[dict]): Retrieved precedent cases (each with ``application_id``).
        ward (str | None): Ward councillor id, if known.
        use_llm (bool): Whether to attempt the LLM Reasoner before degrading.

    Returns:
        PanelOutput: Post-Skeptic per-councillor probabilities, the per-councillor traces,
        the mode, and the precedent ids.
    """
    global_logit = retrieval.global_logit(profiles)
    valid_precedent_ids = {str(c["application_id"]) for c in similar if c.get("application_id")}
    precedent_detail = {
        str(c["application_id"]): f"{c.get('summary', '')} -> {c.get('outcome', '')}"
        for c in similar
        if c.get("application_id")
    }

    claims: dict[str, dict] = {}
    mode = "fallback"
    if use_llm:
        # Chunk the roster so each Reasoner call stays within the model's token/latency budget;
        # a failed chunk simply leaves its councillors for the Skeptic to abstain. The chunks
        # are independent — disjoint councillors merged into one dict — so we run them
        # concurrently: the output is identical, but the wall-clock collapses from the sum of
        # the calls to the slowest single call when Ollama is configured for parallel requests.
        chunks = [
            councillors[start : start + config.REASONER_BATCH_SIZE]
            for start in range(0, len(councillors), config.REASONER_BATCH_SIZE)
        ]

        def _reason_chunk(chunk: list[str]) -> dict[str, dict]:
            context = retrieval.format_context(application, chunk, profiles, staff_rec, similar)
            return run_reasoner_llm(context, chunk)

        workers = max(1, min(len(chunks), config.REASONER_MAX_PARALLEL))
        if workers <= 1:
            for chunk in chunks:
                claims.update(_reason_chunk(chunk))
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                for result in pool.map(_reason_chunk, chunks):
                    claims.update(result)
        if claims:
            mode = "panel"
    if not claims:
        claims = deterministic_claims(
            application, councillors, profiles, staff_signal, ward, global_logit
        )

    traces: list[CouncillorReasoning] = []
    per: dict[str, float] = {}
    for cid in councillors:
        reasoning = skeptic_review(
            cid,
            claims.get(cid, {}),
            profiles.get(cid),
            valid_precedent_ids,
            precedent_detail,
            staff_rec,
            global_logit,
        )
        traces.append(reasoning)
        per[cid] = reasoning.p_yes
    return PanelOutput(
        per_councillor=per,
        traces=traces,
        mode=mode,
        precedent_ids=sorted(valid_precedent_ids),
    )
