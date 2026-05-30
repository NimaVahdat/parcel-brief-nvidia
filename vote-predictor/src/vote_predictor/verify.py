"""The agentic verification layer: three independent LLM verifiers + a deterministic consensus.

This runs *after* — and only on claims that already passed — the deterministic Skeptic gate in
``panel.py``. The gate is the hard floor (an ungrounded claim is forced to a flagged prior and
no LLM may override that). This layer cross-examines the survivors:

* **Evidence-Verifier** — re-reads the councillor record, staff recommendation, and cited
  precedent and confirms the evidence actually supports the stated ``p_yes`` (flags overreach).
* **Skeptic-Critic** — adversarially argues the OPPOSITE vote; if that case cannot be rebutted
  from the cited evidence, the claim is not safely supported and is pulled toward the prior.
* **Precedent-Checker** — re-resolves each cited precedent id against the live corpus (a
  deterministic lookup, independent of retrieval) and judges whether the re-resolved record is
  genuinely analogous, not a spurious embedding match.

The verifiers vote; a **deterministic** consensus (``consensus``) turns the votes into a final
probability. The consensus can only **downgrade** (widen uncertainty toward the grounded prior)
or **abstain** (fall back to the prior) — a hard clamp guarantees it can never move a claim
*away* from the prior, so no verifier can upgrade a claim past the deterministic gate. When the
model is unreachable mid-run the layer is a no-op and the gate's result stands unchanged.

All inference is local (nemotron-3-super via Ollama), temperature 0, strict-JSON outputs that
are Pydantic-validated; verifier nondeterminism is treated as a risk the eval gate measures
(see ``eval.measure_verifier_stability``), not something waved away.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from vote_predictor import config
from vote_predictor.schemas import (
    PrecedentJudgment,
    ReasoningBasis,
    VerificationRecord,
    VerificationVerdict,
    VerifierName,
    VerifierVote,
)

logger = logging.getLogger(__name__)

#: Hard upper bound on per-councillor entries accepted from one verifier response. Far above any
#: real committee roster (so a legitimate reply is never dropped), it caps the work done on a
#: pathological or hallucinated response that returns a huge map of fabricated ids.
_MAX_VERIFIER_ENTRIES = 500

_EVIDENCE_SYSTEM = (
    "You are an evidence auditor on a Toronto council-vote panel. A first analyst proposed, for "
    "each councillor, a probability of a YES vote with cited evidence. Your ONLY job is to judge "
    "whether the cited evidence actually supports that probability at its stated confidence. "
    "Reason ONLY from the evidence shown — the councillor's own voting record, the city staff "
    "recommendation, and the listed precedent outcomes. Mark supported=false when the probability "
    "overreaches the evidence: e.g. it sits far from the councillor's own yes-rate with no "
    "precedent backing, or it is a confident number drawn from thin evidence. Invent no facts. "
    "Respond with STRICT JSON only."
)

_CRITIC_SYSTEM = (
    "You are an adversarial critic on a Toronto council-vote panel. For each councillor a first "
    "analyst proposed a probability of a YES vote. Argue the OPPOSITE outcome as strongly as the "
    "cited evidence allows, then judge whether that opposite case can be REBUTTED using only the "
    "cited evidence. If the opposite vote stays plausible and you cannot rebut it from the "
    "evidence, the claim is NOT safely supported — mark supported=false and the panel will widen "
    "its uncertainty toward the grounded prior. Mark supported=true ONLY when the cited evidence "
    "clearly defeats the opposite case. Reason ONLY from the shown evidence; invent nothing. "
    "Respond with STRICT JSON only."
)

_PRECEDENT_SYSTEM = (
    "You are a precedent auditor on a Toronto council-vote panel. You are given a SUBJECT "
    "development application and precedent applications that were cited as comparable. For EACH "
    "precedent, judge whether it is genuinely analogous to the subject — comparable in scale "
    "(units, height), use type, affordability, and variance burden — as opposed to a superficial "
    "or spurious match. Reason ONLY from the summaries shown. Invent no facts. Respond with "
    "STRICT JSON only."
)


@dataclass(frozen=True)
class VerifiedClaim:
    """The verification layer's resolution of one gate-passed claim.

    Attributes:
        p_yes (float): The shipped probability after verification (== the gate's value when
            confirmed; pulled toward the prior when downgraded; the prior when abstained).
        grounded (bool): True unless the verifiers abstained the claim to its prior.
        basis (ReasoningBasis): The grounding basis after verification (``prior`` on abstain).
        record (VerificationRecord): The auditable verification trace (votes + consensus).
    """

    p_yes: float
    grounded: bool
    basis: ReasoningBasis
    record: VerificationRecord


def _coerce_bool(value: object) -> bool | None:
    """Coerce a model's loosely-typed truthy field to a strict bool, or ``None`` if unrecognizable.

    Tolerates JSON booleans, integer 0/1, and the string spellings a reasoning model occasionally
    emits ("true"/"yes"/"1"). Returns ``None`` for anything else — a float confidence score, a
    word like "partially", ``null`` — so the caller can treat an unparseable verdict as a vote
    that *did not render* rather than fabricating a (possibly wrong) boolean from noise.

    Args:
        value (object): The raw value from the parsed verifier JSON.

    Returns:
        bool | None: The coerced boolean, or ``None`` when ``value`` is not a recognizable boolean.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):  # bool is an int subclass, already handled above
        return value != 0
    if isinstance(value, str):
        token = value.strip().lower()
        if token in ("true", "yes", "y", "1", "supported"):
            return True
        if token in ("false", "no", "n", "0", "unsupported"):
            return False
    return None


def _per_councillor_votes(
    raw: dict, verifier: VerifierName, councillor_ids: list[str]
) -> dict[str, VerifierVote]:
    """Parse a batched verifier response into per-councillor votes (skipping unusable entries).

    Args:
        raw (dict): The parsed JSON from a verifier call, expected to carry a
            ``per_councillor`` map of ``{id: {"supported", "reason"}}``.
        verifier (VerifierName): The verifier name to stamp on each vote.
        councillor_ids (list[str]): The ids the call was asked about; only these are accepted.

    Returns:
        dict[str, VerifierVote]: One vote per councillor the model returned usably. A councillor
        the model omitted, or whose ``supported`` value is missing or not a recognizable boolean,
        is absent — treated downstream as "this verifier did not vote on that councillor", never
        as an implicit unsupported vote (so a parse glitch cannot fabricate a dissent).
    """
    per = raw.get("per_councillor", {}) if isinstance(raw, dict) else {}
    if not isinstance(per, dict) or len(per) > _MAX_VERIFIER_ENTRIES:
        return {}  # not a usable map, or a pathological response with far too many keys
    allowed = set(councillor_ids)
    votes: dict[str, VerifierVote] = {}
    for cid, entry in per.items():
        if cid not in allowed or not isinstance(entry, dict):
            continue
        supported = _coerce_bool(entry.get("supported"))
        if supported is None:  # missing or unparseable verdict -> no usable vote
            continue
        votes[cid] = VerifierVote(
            verifier=verifier,
            supported=supported,
            reason=str(entry.get("reason", "") or "").strip()[:240],
        )
    return votes


def _claims_block(
    chunk: list,
    profiles: dict[str, dict],
    staff_rec: str,
    resolved_precedents: dict[str, dict],
) -> str:
    """Render the per-councillor evidence + claim block fed to the Evidence-Verifier and Critic.

    Args:
        chunk (list): A list of gate-passed ``CouncillorReasoning`` traces to verify.
        profiles (dict[str, dict]): Councillor profiles (for the record shown to the verifiers).
        staff_rec (str): The staff recommendation key.
        resolved_precedents (dict[str, dict]): Re-resolved precedent records keyed by id.

    Returns:
        str: A plain-text block listing each councillor's claim and the evidence behind it.
    """
    lines = [f"STAFF RECOMMENDATION: {staff_rec}", "", "CLAIMS TO AUDIT:"]
    for trace in chunk:
        cid = trace.councillor_id
        profile = profiles.get(cid) or {}
        n_votes = int(profile.get("n_votes", 0) or 0)
        # Mirror the gate's usability threshold so the verifier judges the same evidence the gate
        # counted — a sub-threshold record is shown as "no usable record", not as grounding.
        if n_votes >= config.MIN_GROUNDING_VOTES:
            record = (
                f"{profile.get('lean', 'unknown')} lean, voted Yes "
                f"{profile.get('yes_rate', 0):.0%} of {n_votes} recorded votes"
            )
        else:
            record = "no usable voting record (below the grounding threshold)"
        cited = [e.ref_id for e in trace.evidence if e.kind == "precedent"]
        prec_lines = []
        for pid in cited:
            detail = resolved_precedents.get(pid)
            shown = (
                f"{detail.get('summary', '')} -> {detail.get('outcome', 'unknown')}"
                if detail
                else "did not re-resolve"
            )
            prec_lines.append(f"      [{pid}] {shown}")
        lines.append(
            f"  - councillor {cid}: claims p_yes={trace.p_yes:.2f} "
            f"(prior {trace.prior_p_yes if trace.prior_p_yes is not None else 'n/a'}).\n"
            f"      record: {record}\n"
            f'      rationale: "{trace.rationale}"\n'
            f"      cited precedent:\n" + ("\n".join(prec_lines) if prec_lines else "      (none)")
        )
    return "\n".join(lines)


def _chat_json(messages: list[dict]) -> dict:
    """Call the local model for a strict-JSON verifier response (returns {} on any failure).

    Args:
        messages (list[dict]): OpenAI-style chat messages for the verifier.

    Returns:
        dict: The parsed JSON object, or ``{}`` if the endpoint is unreachable or the response
        is empty/unparseable (the caller treats an empty result as "this verifier did not run").
    """
    from vote_predictor import llm_wrapper

    try:
        return llm_wrapper.chat_json(messages, temperature=0.0)
    except ImportError:
        # A genuine misconfiguration (no LLM client), not a transient miss. Surface it loudly so a
        # broken install is not silently mistaken for a clean run, but still degrade to "no vote"
        # so the deterministic gate result stands.
        logger.warning("verifier: LLM client unavailable; verification degraded to 'unverified'")
        return {}
    except Exception as exc:  # noqa: BLE001 - transient failure leaves the gate result to stand
        logger.debug("verifier call failed (%s); treating as no vote", type(exc).__name__)
        return {}


def run_evidence_verifier(block: str, councillor_ids: list[str]) -> dict[str, VerifierVote]:
    """Run the Evidence-Verifier over a chunk of claims and return per-councillor votes.

    Args:
        block (str): The rendered claims/evidence block from ``_claims_block``.
        councillor_ids (list[str]): The councillor ids in this chunk.

    Returns:
        dict[str, VerifierVote]: Evidence-Verifier votes keyed by councillor id ({} on failure).
    """
    user = (
        f"{block}\n\n"
        "For EVERY councillor above, decide whether the cited evidence supports the stated "
        "p_yes at its confidence. Return STRICT JSON of exactly this shape:\n"
        '{"per_councillor": {"<id>": {"supported": true, "reason": "<one line>"}}}'
    )
    raw = _chat_json(
        [{"role": "system", "content": _EVIDENCE_SYSTEM}, {"role": "user", "content": user}]
    )
    return _per_councillor_votes(raw, "evidence", councillor_ids)


def run_skeptic_critic(block: str, councillor_ids: list[str]) -> dict[str, VerifierVote]:
    """Run the Skeptic-Critic over a chunk of claims and return per-councillor votes.

    Args:
        block (str): The rendered claims/evidence block from ``_claims_block``.
        councillor_ids (list[str]): The councillor ids in this chunk.

    Returns:
        dict[str, VerifierVote]: Skeptic-Critic votes keyed by councillor id ({} on failure).
        ``supported=True`` means the claim survived the adversarial challenge.
    """
    user = (
        f"{block}\n\n"
        "For EVERY councillor above, argue the opposite (a NO vote where p_yes>0.5, or a YES "
        "where p_yes<0.5), then judge if that opposite case is rebuttable from the cited "
        "evidence. Return STRICT JSON of exactly this shape:\n"
        '{"per_councillor": {"<id>": {"supported": true, "reason": "<one line>"}}}\n'
        "supported=true ONLY if the cited evidence clearly defeats the opposite case."
    )
    raw = _chat_json(
        [{"role": "system", "content": _CRITIC_SYSTEM}, {"role": "user", "content": user}]
    )
    return _per_councillor_votes(raw, "skeptic_critic", councillor_ids)


def run_precedent_checker(
    application_summary: str,
    cited_ids: set[str],
    resolved_precedents: dict[str, dict],
) -> dict[str, PrecedentJudgment]:
    """Re-resolve and judge each cited precedent id (deterministic resolution + LLM analogousness).

    A cited id that does not re-resolve against the live corpus is recorded as spurious without
    consulting the model. Resolved ids are passed to the Precedent-Checker, which judges whether
    each re-resolved record is genuinely analogous to the subject application.

    Args:
        application_summary (str): A one-line feature summary of the subject application.
        cited_ids (set[str]): All precedent ids cited by gate-passed claims this prediction.
        resolved_precedents (dict[str, dict]): The subset of ``cited_ids`` that re-resolved, with
            their freshly-derived ``summary``/``outcome``.

    Returns:
        dict[str, PrecedentJudgment]: One judgment per cited id. Unresolved ids are marked
        ``resolves=False, analogous=False``; resolved ids carry the model's analogousness verdict
        (defaulting to analogous when the model could not be reached, so re-resolution alone does
        not silently strip grounding on a transient outage).
    """
    judgments: dict[str, PrecedentJudgment] = {}
    for pid in cited_ids:
        if pid not in resolved_precedents:
            judgments[pid] = PrecedentJudgment(
                precedent_id=pid,
                resolves=False,
                analogous=False,
                reason="did not re-resolve to an ingested record (corpus/index drift)",
            )
    if not resolved_precedents:
        return judgments

    lines = [f"SUBJECT APPLICATION: {application_summary}", "", "CITED PRECEDENTS:"]
    for pid, detail in resolved_precedents.items():
        lines.append(f"  - [{pid}] {detail['summary']} -> {detail['outcome']}")
    user = (
        "\n".join(lines) + "\n\n"
        "For EACH precedent id, judge whether it is genuinely analogous to the subject. "
        "Return STRICT JSON of exactly this shape:\n"
        '{"precedents": {"<id>": {"analogous": true, "reason": "<one line>"}}}'
    )
    raw = _chat_json(
        [{"role": "system", "content": _PRECEDENT_SYSTEM}, {"role": "user", "content": user}]
    )
    per = raw.get("precedents", {}) if isinstance(raw, dict) else {}
    per = per if isinstance(per, dict) else {}
    for pid in resolved_precedents:
        entry = per.get(pid) if isinstance(per.get(pid), dict) else {}
        # Default analogous=True when the model returned nothing usable for this id: the id DID
        # re-resolve, so a transient model miss should not by itself strip the grounding (the
        # Evidence-Verifier and Skeptic-Critic still cross-examine the claim).
        coerced = _coerce_bool(entry.get("analogous")) if entry else None
        analogous = True if coerced is None else coerced
        judgments[pid] = PrecedentJudgment(
            precedent_id=pid,
            resolves=True,
            analogous=analogous,
            reason=str(entry.get("reason", "") or "").strip()[:240] if entry else "re-resolved",
        )
    return judgments


def consensus(
    *,
    p_yes_gate: float,
    prior: float,
    basis: ReasoningBasis,
    has_record: bool,
    cited_precedent_ids: list[str],
    evidence_vote: VerifierVote | None,
    critic_vote: VerifierVote | None,
    precedent_judgments: dict[str, PrecedentJudgment],
) -> VerifiedClaim:
    """Combine the verifier votes into a final probability — deterministically, and only weaker.

    This is the structural guarantee of the verification layer: it is pure arithmetic over the
    votes, and the final probability is hard-clamped to the interval between the prior and the
    gate's value, so no verifier (or future bug) can push a claim further from the prior than the
    deterministic gate already allowed. Verifiers can only confirm, downgrade, or abstain.

    Rules: a spurious sole-precedent grounding (cited precedent does not re-resolve / is not
    analogous, and the councillor has no usable record) abstains to the prior. Otherwise: all
    verifiers supporting -> confirm; a single withheld vote -> downgrade toward the prior; a
    majority (``config.VERIFIER_ABSTAIN_MIN_DISSENT``) withholding -> abstain. With no verifier
    reachable, the gate result stands unchanged (``unverified``).

    Args:
        p_yes_gate (float): The probability the deterministic gate shipped.
        prior (float): The councillor's grounded prior (the abstain target / clamp boundary).
        basis (ReasoningBasis): The gate's grounding basis (kept unless the layer abstains).
        has_record (bool): Whether the councillor has a usable voting record.
        cited_precedent_ids (list[str]): Precedent ids this claim cited (drives the Precedent
            verifier's applicability).
        evidence_vote (VerifierVote | None): The Evidence-Verifier's vote, or None if it did not run.
        critic_vote (VerifierVote | None): The Skeptic-Critic's vote, or None if it did not run.
        precedent_judgments (dict[str, PrecedentJudgment]): Per-precedent checks for cited ids.

    Returns:
        VerifiedClaim: The post-verification probability, grounding, and auditable record.
    """
    votes: list[VerifierVote] = []
    if evidence_vote is not None:
        votes.append(evidence_vote)
    if critic_vote is not None:
        votes.append(critic_vote)

    prec_used: list[PrecedentJudgment] = []
    precedent_vote: VerifierVote | None = None
    if cited_precedent_ids:
        for pid in cited_precedent_ids:
            prec_used.append(
                precedent_judgments.get(pid)
                or PrecedentJudgment(
                    precedent_id=pid, resolves=False, analogous=False, reason="not checked"
                )
            )
        prec_supported = any(j.resolves and j.analogous for j in prec_used)
        precedent_vote = VerifierVote(
            verifier="precedent_checker",
            supported=prec_supported,
            reason=(
                "at least one cited precedent re-resolved and is analogous"
                if prec_supported
                else "no cited precedent re-resolved to an analogous record"
            ),
        )
        votes.append(precedent_vote)

    record = VerificationRecord(
        verdict="unverified",
        votes=votes,
        precedent_judgments=prec_used,
        pre_verification_p_yes=round(p_yes_gate, 4),
    )

    def _finish(
        verdict: VerificationVerdict,
        final: float,
        grounded: bool,
        out_basis: ReasoningBasis,
        note: str,
    ) -> VerifiedClaim:
        """Apply the hard clamp, stamp the record, and build the VerifiedClaim.

        Args:
            verdict (VerificationVerdict): The consensus disposition to stamp on the record.
            final (float): The pre-clamp probability the chosen branch wants to ship.
            grounded (bool): Whether the shipped probability is still evidence-grounded.
            out_basis (ReasoningBasis): The grounding basis to report (``prior`` on abstain).
            note (str): The one-line consensus explanation.

        Returns:
            VerifiedClaim: The clamped, stamped resolution for this councillor.
        """
        # HARD CLAMP — the verification layer can only move toward the prior, never away. This
        # single line is what makes "verifiers can never upgrade a claim past the deterministic
        # gate" a structural fact rather than a property of the (LLM-fed) branch logic above.
        lo, hi = (prior, p_yes_gate) if prior <= p_yes_gate else (p_yes_gate, prior)
        clamped = min(max(final, lo), hi)
        return VerifiedClaim(
            p_yes=round(clamped, 4),
            grounded=grounded,
            basis=out_basis,
            record=record.model_copy(update={"verdict": verdict, "note": note}),
        )

    if not votes:
        return _finish("unverified", p_yes_gate, True, basis, "no verifier reachable; gate stands")

    unsupported = [v for v in votes if not v.supported]

    # The cited precedent was the only grounding and it did not hold up -> abstain.
    if precedent_vote is not None and not precedent_vote.supported and not has_record:
        return _finish(
            "abstained",
            prior,
            False,
            "prior",
            "sole grounding was a cited precedent that did not re-resolve or was not analogous; "
            "abstained to prior",
        )

    if not unsupported:
        return _finish(
            "confirmed",
            p_yes_gate,
            True,
            basis,
            "all verifiers concurred the evidence supports the claim",
        )

    if len(unsupported) >= config.VERIFIER_ABSTAIN_MIN_DISSENT:
        names = ", ".join(v.verifier for v in unsupported)
        return _finish(
            "abstained",
            prior,
            False,
            "prior",
            f"{len(unsupported)} of {len(votes)} verifiers withheld support ({names}); abstained to prior",
        )

    pulled = p_yes_gate + config.VERIFIER_DOWNGRADE_PULL * (prior - p_yes_gate)
    # If the cited precedent was the dissenter but a councillor record still backs the claim, the
    # residual grounding is the record — report that basis, not the precedent that was discredited.
    out_basis: ReasoningBasis = basis
    if (
        basis == "precedent"
        and has_record
        and precedent_vote is not None
        and not precedent_vote.supported
    ):
        out_basis = "record"
    return _finish(
        "downgraded",
        pulled,
        True,
        out_basis,
        f"{unsupported[0].verifier} withheld support; uncertainty widened toward the prior",
    )


def verify_panel(
    gate_traces: list,
    profiles: dict[str, dict],
    staff_rec: str,
    application_summary: str,
    resolve_precedents: Callable[[set[str]], dict[str, dict]] | None = None,
) -> dict[str, VerifiedClaim]:
    """Cross-examine every gate-passed claim with the three verifiers and apply the consensus.

    Only ``grounded`` claims are verified — an already-abstained claim sits at its prior (the
    gate's floor), which the layer cannot improve on. The Precedent-Checker runs once over the
    union of cited precedent; the Evidence-Verifier and Skeptic-Critic run over the grounded
    councillors in ``config.REASONER_BATCH_SIZE`` chunks, concurrently (the result is identical
    to running them serially; only the wall-clock changes).

    Args:
        gate_traces (list): The per-councillor ``CouncillorReasoning`` traces from the gate.
        profiles (dict[str, dict]): Councillor profiles (for the record shown to the verifiers).
        staff_rec (str): The staff recommendation key.
        application_summary (str): A one-line feature summary of the subject application.
        resolve_precedents (Callable | None): Resolver mapping a set of precedent ids to their
            re-resolved records; defaults to ``retrieval.resolve_precedents`` (injectable for tests).

    Returns:
        dict[str, VerifiedClaim]: One resolution per grounded councillor id. Councillors the gate
        already abstained are absent (left untouched by the caller).
    """
    # Verify only grounded claims that carry a real prior. The gate always sets ``prior_p_yes``
    # on a grounded trace, so the prior filter is normally a no-op; it guarantees ``consensus``
    # receives a genuine prior to pull toward, rather than silently falling back to the gate value
    # (which would neutralize an abstain — shipping the gate value while flagging it "prior").
    grounded = [t for t in gate_traces if t.grounded and t.prior_p_yes is not None]
    if not grounded:
        return {}

    if resolve_precedents is None:
        from vote_predictor import retrieval

        resolve_precedents = retrieval.resolve_precedents

    cited_by_councillor: dict[str, list[str]] = {
        t.councillor_id: [e.ref_id for e in t.evidence if e.kind == "precedent"] for t in grounded
    }
    cited_ids = {pid for ids in cited_by_councillor.values() for pid in ids}
    resolved = resolve_precedents(cited_ids) if cited_ids else {}
    precedent_judgments = (
        run_precedent_checker(application_summary, cited_ids, resolved) if cited_ids else {}
    )

    chunks = [
        grounded[start : start + config.REASONER_BATCH_SIZE]
        for start in range(0, len(grounded), config.REASONER_BATCH_SIZE)
    ]

    def _verify_chunk(chunk: list) -> tuple[dict[str, VerifierVote], dict[str, VerifierVote]]:
        """Run the Evidence-Verifier and Skeptic-Critic over one chunk of grounded claims."""
        ids = [t.councillor_id for t in chunk]
        block = _claims_block(chunk, profiles, staff_rec, resolved)
        return run_evidence_verifier(block, ids), run_skeptic_critic(block, ids)

    evidence_votes: dict[str, VerifierVote] = {}
    critic_votes: dict[str, VerifierVote] = {}
    workers = max(1, min(len(chunks), config.VERIFIER_MAX_PARALLEL))
    if workers <= 1:
        results = [_verify_chunk(chunk) for chunk in chunks]
    else:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_verify_chunk, chunks))
    for ev_map, cr_map in results:
        evidence_votes.update(ev_map)
        critic_votes.update(cr_map)

    out: dict[str, VerifiedClaim] = {}
    for trace in grounded:
        cid = trace.councillor_id
        has_record = any(e.kind == "councillor_record" for e in trace.evidence)
        out[cid] = consensus(
            p_yes_gate=trace.p_yes,
            prior=trace.prior_p_yes,  # guaranteed non-None by the grounded filter above
            basis=trace.basis,
            has_record=has_record,
            cited_precedent_ids=cited_by_councillor[cid],
            evidence_vote=evidence_votes.get(cid),
            critic_vote=critic_votes.get(cid),
            precedent_judgments=precedent_judgments,
        )
    return out
