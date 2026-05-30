"""Pydantic types for vote-predictor.

The first three types — ``ApplicationFeatures``, ``Lever``, ``VotePrediction`` — are the
frozen Contract 1 surface (see docs/CONTRACTS.md) and must not change shape. The remaining
types are an *additive*, non-contract evidence trace: they let the service and UI show how
the multi-agent panel reasoned, without touching the contract. Nothing in Contract 1 or
Contract 5's required fields depends on them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --- Contract 1 (FROZEN — do not change shape) -----------------------------------


class ApplicationFeatures(BaseModel):
    parcel_id: str
    height_m: float
    total_units: int
    affordable_units: int
    retail_sqft: float
    use_mix: dict[str, float]
    neighborhood: str
    requested_variances: list[str] = []
    #: Optional, additive: the ward councillor's id. When the caller (connector) supplies it,
    #: the ward-councillor bonus is applied; absent, it is simply not used. Optional with a
    #: default, so this does not change Contract 1's required shape.
    ward_councillor_id: str | None = None


class Lever(BaseModel):
    change: str
    delta_probability: float


class VotePrediction(BaseModel):
    approval_probability: float
    per_councillor: dict[str, float]
    swing_councillors: list[str]
    levers: list[Lever]


# --- Additive evidence trace (NOT a contract type) -------------------------------

#: How a per-councillor probability is grounded. ``record`` = the councillor's own voting
#: history; ``precedent`` = a retrieved similar application's outcome; ``staff`` = the staff
#: recommendation; ``prior`` = no application-specific grounding, abstained to a prior.
ReasoningBasis = Literal["record", "precedent", "staff", "prior"]

#: The Skeptic's disposition for a Reasoner claim.
SkepticVerdict = Literal[
    "accepted",
    "rejected_uncited",
    "forced_abstain",
    "downgraded_overconfident",
]

#: Which of the three independent LLM verifiers produced a vote.
VerifierName = Literal["evidence", "skeptic_critic", "precedent_checker"]

#: The agentic verification layer's disposition for a *gate-passed* claim. ``confirmed`` =
#: all verifiers that ran agreed the evidence supports the claim; ``downgraded`` = one verifier
#: withheld support, so the probability was pulled toward the prior (uncertainty widened);
#: ``abstained`` = a majority withheld support (or the sole precedent grounding was spurious),
#: so the claim fell back to the prior; ``unverified`` = no verifier could be reached, so the
#: deterministic gate's result stands unchanged. The layer can never move a claim *away* from
#: the prior — it only downgrades or abstains (see ``verify.py``).
VerificationVerdict = Literal["confirmed", "downgraded", "abstained", "unverified"]


class EvidenceRef(BaseModel):
    """A single piece of evidence a Reasoner cited for a per-councillor probability.

    Attributes:
        kind (str): The evidence type — councillor record, precedent application, or staff rec.
        ref_id (str): A stable id for the evidence (councillor id, application id, or item id).
        detail (str): A short human-readable description of what the evidence shows.
    """

    kind: Literal["councillor_record", "precedent", "staff_rec"]
    ref_id: str
    detail: str


class VerifierVote(BaseModel):
    """One independent verifier's judgment of a gate-passed claim.

    Attributes:
        verifier (VerifierName): Which verifier produced this vote.
        supported (bool): True if the verifier judges the cited evidence supports the claim's
            stated confidence (for the Skeptic-Critic, True means the claim survived the
            adversarial challenge; for the Precedent-Checker, that at least one cited precedent
            re-resolved to a real record and is genuinely analogous).
        reason (str): The verifier's one-line justification.
    """

    verifier: VerifierName
    supported: bool
    reason: str = ""


class PrecedentJudgment(BaseModel):
    """The Precedent-Checker's verdict on a single cited precedent application id.

    Attributes:
        precedent_id (str): The cited precedent application id.
        resolves (bool): True if the id re-resolves to a real ingested record (a deterministic
            corpus lookup, independent of retrieval time — catches index/corpus drift).
        analogous (bool): True if the re-resolved record is genuinely comparable to the subject
            application (LLM judgment), as opposed to a spurious embedding match.
        reason (str): The Precedent-Checker's one-line justification.
    """

    precedent_id: str
    resolves: bool
    analogous: bool
    reason: str = ""


class VerificationRecord(BaseModel):
    """The agentic verification layer's outcome for one gate-passed claim — additive trace.

    The layer runs three independent LLM verifiers on a claim that already cleared the
    deterministic Skeptic gate, then applies a deterministic consensus that can only weaken the
    claim (pull it toward the prior or abstain) — never strengthen it.

    Attributes:
        verdict (VerificationVerdict): The consensus disposition.
        votes (list[VerifierVote]): The individual verifier votes that ran.
        precedent_judgments (list[PrecedentJudgment]): Per-precedent checks for cited precedent.
        pre_verification_p_yes (float): The gate's shipped probability before verification, so
            the downgrade/abstain is auditable.
        note (str): A one-line explanation of how the consensus was reached.
    """

    verdict: VerificationVerdict
    votes: list[VerifierVote] = Field(default_factory=list)
    precedent_judgments: list[PrecedentJudgment] = Field(default_factory=list)
    pre_verification_p_yes: float
    note: str = ""


class CouncillorReasoning(BaseModel):
    """The full reasoning trace for one councillor: claim, grounding, and Skeptic verdict.

    Attributes:
        councillor_id (str): Normalized councillor id.
        p_yes (float): The shipped probability of a Yes vote (post-Skeptic, post-verification)
            in [0, 1].
        grounded (bool): True if the probability is backed by real evidence; False if it was
            forced to a prior because grounding was absent or the verification layer abstained.
        basis (ReasoningBasis): What the shipped probability rests on.
        rationale (str): One-line rationale (Reasoner's, or the abstain reason).
        evidence (list[EvidenceRef]): The evidence ids the Reasoner cited.
        skeptic_verdict (SkepticVerdict): Whether the deterministic gate accepted, rejected,
            forced to abstain, or pulled back the claim for over-confidence.
        skeptic_note (str): The Skeptic gate's one-line justification.
        prior_p_yes (float | None): The councillor's own profile prior, for transparency.
        verification (VerificationRecord | None): The agentic verification layer's outcome, if
            it ran for this claim (None when the claim was already abstained by the gate, when
            the LLM panel was offline, or when verification is disabled).
    """

    councillor_id: str
    p_yes: float
    grounded: bool
    basis: ReasoningBasis
    rationale: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    skeptic_verdict: SkepticVerdict
    skeptic_note: str = ""
    prior_p_yes: float | None = None
    verification: VerificationRecord | None = None


class AgentTrace(BaseModel):
    """The panel's full reasoning trace for one prediction — the additive service payload.

    Attributes:
        mode (str): ``panel`` (multi-agent on the live model), ``fallback`` (deterministic,
            no model reachable), or ``no_grounding`` (ablation).
        model (str): The model id used (or "deterministic-fallback").
        staff_recommendation (str): The staff recommendation key fed to the panel.
        councillors (list[CouncillorReasoning]): Per-councillor reasoning traces.
        precedent_ids (list[str]): Application ids retrieved as precedent for this prediction.
        n_grounded (int): Number of councillors whose probability is evidence-grounded (after
            both the deterministic gate and the verification layer).
        n_abstained (int): Number forced to a prior for lack of grounding (gate or verifier).
        verification_enabled (bool): Whether the agentic verification layer ran this prediction.
        n_verified (int): Gate-passed claims the verifiers confirmed unchanged.
        n_verifier_downgraded (int): Gate-passed claims the verifiers pulled toward the prior.
        n_verifier_abstained (int): Gate-passed claims the verifiers abstained to the prior.
        notes (str): Free-text notes (e.g. degraded-mode reason).
    """

    mode: Literal["panel", "fallback", "no_grounding"]
    model: str
    staff_recommendation: str
    councillors: list[CouncillorReasoning] = Field(default_factory=list)
    precedent_ids: list[str] = Field(default_factory=list)
    n_grounded: int = 0
    n_abstained: int = 0
    verification_enabled: bool = False
    n_verified: int = 0
    n_verifier_downgraded: int = 0
    n_verifier_abstained: int = 0
    notes: str = ""
