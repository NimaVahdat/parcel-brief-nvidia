"""Tests for the agentic verification layer.

The headline invariant: the verification layer can only move a gate-passed claim TOWARD its
prior (downgrade) or all the way to it (abstain) — never away. These tests prove that with a
deterministic ``consensus`` (no LLM) and an integration path where the LLM verifiers are faked.
"""

from __future__ import annotations

import pytest
from vote_predictor import config, panel, verify
from vote_predictor.schemas import (
    CouncillorReasoning,
    EvidenceRef,
    PrecedentJudgment,
    VerifierVote,
)


def _vote(verifier: str, supported: bool) -> VerifierVote:
    """Build a VerifierVote for one verifier with a given support flag."""
    return VerifierVote(verifier=verifier, supported=supported, reason="test")


def _consensus(
    *,
    gate=0.9,
    prior=0.5,
    basis="record",
    has_record=True,
    cited=None,
    evidence=True,
    critic=True,
    precedent_judgments=None,
):
    """Run consensus with convenient defaults (votes given as bool|None)."""
    return verify.consensus(
        p_yes_gate=gate,
        prior=prior,
        basis=basis,
        has_record=has_record,
        cited_precedent_ids=cited or [],
        evidence_vote=None if evidence is None else _vote("evidence", evidence),
        critic_vote=None if critic is None else _vote("skeptic_critic", critic),
        precedent_judgments=precedent_judgments or {},
    )


# --- consensus: the deterministic core --------------------------------------------


def test_consensus_all_support_confirms_unchanged():
    """All verifiers supporting -> confirm; the gate's probability ships unchanged."""
    out = _consensus(gate=0.82, prior=0.5, evidence=True, critic=True)
    assert out.record.verdict == "confirmed"
    assert out.p_yes == 0.82
    assert out.grounded is True
    assert out.basis == "record"


def test_consensus_single_dissent_downgrades_toward_prior():
    """One verifier withholding support -> downgrade halfway toward the prior (uncertainty widens)."""
    out = _consensus(gate=0.9, prior=0.5, evidence=False, critic=True)
    assert out.record.verdict == "downgraded"
    assert out.p_yes == pytest.approx(0.7)  # 0.9 + 0.5*(0.5-0.9)
    assert out.grounded is True
    assert 0.5 < out.p_yes < 0.9  # strictly between gate and prior


def test_consensus_majority_dissent_abstains_to_prior():
    """A majority withholding support -> abstain to the prior, flagged not grounded."""
    out = _consensus(gate=0.95, prior=0.5, evidence=False, critic=False)
    assert out.record.verdict == "abstained"
    assert out.p_yes == 0.5
    assert out.grounded is False
    assert out.basis == "prior"


def test_consensus_no_verifier_ran_leaves_gate_unchanged():
    """No verifier reachable and no precedent -> unverified; the gate result stands."""
    out = _consensus(gate=0.77, prior=0.5, evidence=None, critic=None, cited=[])
    assert out.record.verdict == "unverified"
    assert out.p_yes == 0.77
    assert out.grounded is True


def test_consensus_spurious_sole_precedent_abstains():
    """A precedent-only claim whose cited precedent is spurious abstains, even if others support."""
    judgments = {"APP1": PrecedentJudgment(precedent_id="APP1", resolves=False, analogous=False)}
    out = _consensus(
        gate=0.85,
        prior=0.5,
        basis="precedent",
        has_record=False,
        cited=["APP1"],
        evidence=True,
        critic=True,
        precedent_judgments=judgments,
    )
    assert out.record.verdict == "abstained"
    assert out.p_yes == 0.5
    assert out.grounded is False


def test_consensus_spurious_precedent_with_record_only_downgrades():
    """When a record still backs the claim, a spurious precedent is one dissent -> downgrade, not abstain."""
    judgments = {"APP1": PrecedentJudgment(precedent_id="APP1", resolves=True, analogous=False)}
    out = _consensus(
        gate=0.9,
        prior=0.5,
        basis="precedent",
        has_record=True,
        cited=["APP1"],
        evidence=True,
        critic=True,
        precedent_judgments=judgments,
    )
    assert out.record.verdict == "downgraded"
    assert 0.5 < out.p_yes < 0.9


def test_consensus_analogous_precedent_supports():
    """A cited precedent that re-resolves and is analogous counts as a supporting precedent vote."""
    judgments = {"APP1": PrecedentJudgment(precedent_id="APP1", resolves=True, analogous=True)}
    out = _consensus(
        gate=0.8,
        prior=0.5,
        basis="precedent",
        has_record=False,
        cited=["APP1"],
        evidence=True,
        critic=True,
        precedent_judgments=judgments,
    )
    assert out.record.verdict == "confirmed"
    assert out.p_yes == 0.8


# --- consensus: the hard clamp (the structural guarantee) -------------------------


@pytest.mark.parametrize("gate,prior", [(0.9, 0.5), (0.3, 0.5), (0.5, 0.5), (0.05, 0.95)])
def test_consensus_never_moves_away_from_prior(gate, prior):
    """Across confirm/downgrade/abstain, the output never lands further from the prior than the gate."""
    lo, hi = sorted((gate, prior))
    for ev in (True, False):
        for cr in (True, False):
            out = _consensus(gate=gate, prior=prior, evidence=ev, critic=cr)
            assert lo - 1e-9 <= out.p_yes <= hi + 1e-9


def test_consensus_clamp_caps_an_overshooting_downgrade(monkeypatch):
    """Even a pull factor > 1 cannot push a downgrade past the prior — the clamp holds the floor."""
    monkeypatch.setattr(config, "VERIFIER_DOWNGRADE_PULL", 5.0)
    out = _consensus(gate=0.9, prior=0.5, evidence=False, critic=True)
    assert out.record.verdict == "downgraded"
    assert out.p_yes == 0.5  # 0.9 + 5*(0.5-0.9) = -1.1, clamped up to the prior


def test_consensus_cannot_upgrade_a_below_prior_claim():
    """A claim below its prior is never pushed above the gate value by any verdict."""
    confirm = _consensus(gate=0.3, prior=0.6, evidence=True, critic=True)
    assert confirm.p_yes == 0.3  # confirmed stays at the gate, not nudged up toward 0.6
    downgrade = _consensus(gate=0.3, prior=0.6, evidence=False, critic=True)
    assert 0.3 < downgrade.p_yes < 0.6  # toward prior (up), but never past it


def test_consensus_full_pull_lands_on_prior_but_stays_grounded(monkeypatch):
    """Pull factor 1.0: a downgrade lands exactly on the prior yet remains grounded (not abstained)."""
    monkeypatch.setattr(config, "VERIFIER_DOWNGRADE_PULL", 1.0)
    out = _consensus(gate=0.9, prior=0.5, evidence=False, critic=True)
    assert out.record.verdict == "downgraded"
    assert out.p_yes == 0.5  # full pull == prior, but a downgrade is not an abstain
    assert out.grounded is True


def test_consensus_downgrade_relabels_basis_when_precedent_spurious_but_record_backs():
    """A spurious cited precedent that only downgrades (record still backs it) re-labels basis=record."""
    judgments = {"APP1": PrecedentJudgment(precedent_id="APP1", resolves=True, analogous=False)}
    out = _consensus(
        gate=0.9,
        prior=0.5,
        basis="precedent",
        has_record=True,
        cited=["APP1"],
        evidence=True,
        critic=True,
        precedent_judgments=judgments,
    )
    assert out.record.verdict == "downgraded"
    assert out.basis == "record"  # the discredited precedent is no longer the stated grounding


# --- model-output coercion ---------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        ("YES", True),
        ("false", False),
        ("unsupported", False),
        ("partially", None),  # an unrecognized word is NOT a vote
        (0.7, None),  # a confidence score is NOT a boolean
        (None, None),
        ({}, None),
    ],
)
def test_coerce_bool(value, expected):
    """_coerce_bool returns a strict bool for recognizable values, else None (no fabricated vote)."""
    assert verify._coerce_bool(value) is expected


def test_per_councillor_votes_skips_unusable_entries():
    """Entries with a missing or unparseable 'supported' are skipped, not coerced to a False vote."""
    raw = {
        "per_councillor": {
            "a": {"supported": True, "reason": "ok"},
            "b": {"supported": "probably"},  # unparseable -> no vote
            "c": {"reason": "no supported key"},  # missing -> no vote
            "z": {"supported": True},  # not in the allowed set -> ignored
        }
    }
    votes = verify._per_councillor_votes(raw, "evidence", ["a", "b", "c"])
    assert set(votes) == {"a"}
    assert votes["a"].supported is True


def test_per_councillor_votes_rejects_pathological_response():
    """A response with far more keys than any real roster is dropped wholesale (DoS guard)."""
    bloated = {str(i): {"supported": True} for i in range(verify._MAX_VERIFIER_ENTRIES + 1)}
    votes = verify._per_councillor_votes({"per_councillor": bloated}, "evidence", ["5"])
    assert votes == {}


# --- verify_panel: orchestration over gate traces ---------------------------------


def _gate_trace(cid, *, p_yes, prior, grounded, basis, record=False, cites=()):
    """Build a gate CouncillorReasoning trace for verify_panel tests."""
    evidence = []
    if record:
        evidence.append(
            EvidenceRef(kind="councillor_record", ref_id=cid, detail="20 votes, 50% Yes")
        )
    for pid in cites:
        evidence.append(EvidenceRef(kind="precedent", ref_id=pid, detail="precedent"))
    return CouncillorReasoning(
        councillor_id=cid,
        p_yes=p_yes,
        grounded=grounded,
        basis=basis,
        rationale="r",
        evidence=evidence,
        skeptic_verdict="accepted" if grounded else "forced_abstain",
        prior_p_yes=prior,
    )


def test_verify_panel_skips_gate_abstained_and_verifies_grounded(monkeypatch):
    """Gate-abstained claims are left untouched; grounded claims are cross-examined."""
    monkeypatch.setattr(
        verify,
        "run_evidence_verifier",
        lambda block, ids: {c: _vote("evidence", True) for c in ids},
    )
    monkeypatch.setattr(
        verify,
        "run_skeptic_critic",
        lambda block, ids: {c: _vote("skeptic_critic", True) for c in ids},
    )

    traces = [
        _gate_trace("grounded", p_yes=0.8, prior=0.5, grounded=True, basis="record", record=True),
        _gate_trace("abstained", p_yes=0.5, prior=0.5, grounded=False, basis="prior"),
    ]
    out = verify.verify_panel(traces, profiles={}, staff_rec="approve", application_summary="x")
    assert set(out) == {"grounded"}  # the gate-abstained claim is never handed to the verifiers
    assert out["grounded"].record.verdict == "confirmed"


def test_verify_panel_abstains_on_spurious_precedent(monkeypatch):
    """A precedent-only claim whose cited id fails re-resolution is abstained by the layer."""
    monkeypatch.setattr(
        verify,
        "run_evidence_verifier",
        lambda block, ids: {c: _vote("evidence", True) for c in ids},
    )
    monkeypatch.setattr(
        verify,
        "run_skeptic_critic",
        lambda block, ids: {c: _vote("skeptic_critic", True) for c in ids},
    )
    # The injected resolver returns nothing -> APP1 does not re-resolve -> spurious.
    traces = [
        _gate_trace("c", p_yes=0.85, prior=0.5, grounded=True, basis="precedent", cites=["APP1"])
    ]
    out = verify.verify_panel(
        traces,
        profiles={},
        staff_rec="unknown",
        application_summary="x",
        resolve_precedents=lambda ids: {},
    )
    assert out["c"].record.verdict == "abstained"
    assert out["c"].p_yes == 0.5
    assert out["c"].grounded is False
    judged = {j.precedent_id: j for j in out["c"].record.precedent_judgments}
    assert judged["APP1"].resolves is False


def test_verify_panel_unverified_when_all_verifiers_fail(monkeypatch):
    """A total verifier outage degrades to 'unverified' — never worse than no verification."""
    monkeypatch.setattr(verify, "run_evidence_verifier", lambda block, ids: {})
    monkeypatch.setattr(verify, "run_skeptic_critic", lambda block, ids: {})
    traces = [_gate_trace("c", p_yes=0.8, prior=0.5, grounded=True, basis="record", record=True)]
    out = verify.verify_panel(traces, profiles={}, staff_rec="approve", application_summary="x")
    assert out["c"].record.verdict == "unverified"
    assert out["c"].p_yes == 0.8  # the gate result stands unchanged


def test_verify_panel_skips_trace_without_a_real_prior(monkeypatch):
    """A grounded trace with no prior_p_yes is left to the gate result, not silently neutralized."""
    monkeypatch.setattr(
        verify,
        "run_evidence_verifier",
        lambda block, ids: {c: _vote("evidence", False) for c in ids},
    )
    monkeypatch.setattr(
        verify,
        "run_skeptic_critic",
        lambda block, ids: {c: _vote("skeptic_critic", False) for c in ids},
    )
    traces = [_gate_trace("c", p_yes=0.8, prior=None, grounded=True, basis="record", record=True)]
    out = verify.verify_panel(traces, profiles={}, staff_rec="approve", application_summary="x")
    assert out == {}  # no real prior to pull toward -> not verified


def test_apply_verification_none_returns_trace_unchanged():
    """panel._apply_verification leaves a trace untouched when there is no verification outcome."""
    trace = _gate_trace("c", p_yes=0.8, prior=0.5, grounded=True, basis="record", record=True)
    assert panel._apply_verification(trace, None) is trace


# --- end-to-end through run_panel -------------------------------------------------

_PROFILE = {
    "councillor_id": "a",
    "committee": "te",
    "n_votes": 20,
    "yes_rate": 0.5,
    "propensity_logit": 0.0,  # prior 0.5
    "lean": "swing",
}
_APP = {"height_m": 40, "total_units": 100, "affordable_units": 10, "retail_sqft": 0}


def test_run_panel_verification_downgrades_condemned_claim(monkeypatch):
    """run_panel: a record-grounded claim both verifiers condemn is abstained to the prior."""
    monkeypatch.setattr(
        panel,
        "run_reasoner_llm",
        lambda ctx, cs: {c: {"p_yes": 0.6, "reason": "x", "cites": []} for c in cs},
    )
    monkeypatch.setattr(
        verify,
        "run_evidence_verifier",
        lambda block, ids: {c: _vote("evidence", False) for c in ids},
    )
    monkeypatch.setattr(
        verify,
        "run_skeptic_critic",
        lambda block, ids: {c: _vote("skeptic_critic", False) for c in ids},
    )
    profiles = {"a": _PROFILE, "b": _PROFILE | {"councillor_id": "b"}}
    out = panel.run_panel(
        _APP, ["a", "b"], profiles, "approve", 1.0, [], None, use_llm=True, use_verify=True
    )
    assert out.mode == "panel"
    assert out.verification_enabled is True
    assert out.n_verifier_abstained == 2
    assert all(t.p_yes == 0.5 for t in out.traces)  # pulled to the 0.5 prior
    assert all(
        t.verification is not None and t.verification.verdict == "abstained" for t in out.traces
    )


def test_run_panel_verification_off_leaves_gate_result(monkeypatch):
    """With use_verify=False the gate's grounded probability ships and no verification trace is set."""
    monkeypatch.setattr(
        panel,
        "run_reasoner_llm",
        lambda ctx, cs: {c: {"p_yes": 0.6, "reason": "x", "cites": []} for c in cs},
    )
    profiles = {"a": _PROFILE}
    out = panel.run_panel(
        _APP, ["a"], profiles, "approve", 1.0, [], None, use_llm=True, use_verify=False
    )
    assert out.verification_enabled is False
    assert out.traces[0].p_yes == 0.6
    assert out.traces[0].verification is None


def test_run_panel_no_verification_in_fallback_mode():
    """Verification never runs without the LLM Reasoner — the deterministic gate stands alone."""
    profiles = {"a": _PROFILE}
    out = panel.run_panel(
        _APP, ["a"], profiles, "approve", 1.0, [], None, use_llm=False, use_verify=True
    )
    assert out.mode == "fallback"
    assert out.verification_enabled is False
    assert out.traces[0].verification is None
