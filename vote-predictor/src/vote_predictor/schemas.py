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


class CouncillorReasoning(BaseModel):
    """The full reasoning trace for one councillor: claim, grounding, and Skeptic verdict.

    Attributes:
        councillor_id (str): Normalized councillor id.
        p_yes (float): The shipped probability of a Yes vote (post-Skeptic) in [0, 1].
        grounded (bool): True if the probability is backed by real evidence; False if it was
            forced to a prior because grounding was absent.
        basis (ReasoningBasis): What the shipped probability rests on.
        rationale (str): One-line rationale (Reasoner's, or the abstain reason).
        evidence (list[EvidenceRef]): The evidence ids the Reasoner cited.
        skeptic_verdict (SkepticVerdict): Whether the claim was accepted, rejected, forced to
            abstain, or pulled back for over-confidence.
        skeptic_note (str): The Skeptic's one-line justification.
        prior_p_yes (float | None): The councillor's own profile prior, for transparency.
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


class AgentTrace(BaseModel):
    """The panel's full reasoning trace for one prediction — the additive service payload.

    Attributes:
        mode (str): ``panel`` (multi-agent on the live model), ``fallback`` (deterministic,
            no model reachable), or ``no_grounding`` (ablation).
        model (str): The model id used (or "deterministic-fallback").
        staff_recommendation (str): The staff recommendation key fed to the panel.
        councillors (list[CouncillorReasoning]): Per-councillor reasoning traces.
        precedent_ids (list[str]): Application ids retrieved as precedent for this prediction.
        n_grounded (int): Number of councillors whose probability is evidence-grounded.
        n_abstained (int): Number forced to a prior for lack of grounding.
        notes (str): Free-text notes (e.g. degraded-mode reason).
    """

    mode: Literal["panel", "fallback", "no_grounding"]
    model: str
    staff_recommendation: str
    councillors: list[CouncillorReasoning] = Field(default_factory=list)
    precedent_ids: list[str] = Field(default_factory=list)
    n_grounded: int = 0
    n_abstained: int = 0
    notes: str = ""
