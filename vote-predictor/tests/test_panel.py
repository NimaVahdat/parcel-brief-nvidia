"""Tests for the multi-agent panel: the deterministic Skeptic gate is the core mechanism."""

from __future__ import annotations

from vote_predictor import panel

_RECORD_PROFILE = {
    "councillor_id": "perks",
    "committee": "toronto-east-york",
    "n_votes": 20,
    "yes_rate": 0.5,
    "propensity_logit": 0.0,  # prior == 0.5
    "lean": "swing",
}


def _review(claim, profile, valid_precedents=frozenset()):
    """Run the Skeptic with sensible defaults for a single claim."""
    return panel.skeptic_review(
        councillor_id="perks",
        claim=claim,
        profile=profile,
        valid_precedent_ids=set(valid_precedents),
        precedent_detail={pid: "precedent" for pid in valid_precedents},
        staff_rec="approve",
        global_logit=0.0,
    )


def test_skeptic_forces_abstain_when_ungrounded():
    """No record and no cites -> abstain to prior, flagged not-grounded (the D3 fix)."""
    r = _review({"p_yes": 0.95, "reason": "vibes", "cites": []}, profile=None)
    assert r.grounded is False
    assert r.basis == "prior"
    assert r.skeptic_verdict == "forced_abstain"
    assert r.p_yes == 0.5  # prior, not the fabricated 0.95


def test_skeptic_rejects_uncited_precedent():
    """A claim citing a precedent id that isn't in the retrieved set is rejected."""
    r = _review(
        {"p_yes": 0.9, "reason": "cited a ghost", "cites": ["DOES-NOT-EXIST"]}, profile=None
    )
    assert r.grounded is False
    assert r.skeptic_verdict == "rejected_uncited"
    assert r.p_yes == 0.5


def test_skeptic_accepts_record_grounded_claim():
    """A claim from a councillor with a real record is accepted (basis=record)."""
    r = _review(
        {"p_yes": 0.62, "reason": "leans yes on infill", "cites": []}, profile=_RECORD_PROFILE
    )
    assert r.grounded is True
    assert r.basis == "record"
    assert r.skeptic_verdict == "accepted"
    assert r.p_yes == 0.62


def test_skeptic_accepts_precedent_grounded_claim():
    """A claim with no record but a valid cited precedent is accepted (basis=precedent)."""
    r = _review(
        {"p_yes": 0.7, "reason": "matches precedent", "cites": ["APP1"]},
        profile=None,
        valid_precedents={"APP1"},
    )
    assert r.grounded is True
    assert r.basis == "precedent"
    assert r.skeptic_verdict == "accepted"


def test_skeptic_downgrades_overconfident_claim():
    """A record-grounded claim far from the prior with no precedent is pulled back toward it."""
    r = _review({"p_yes": 0.97, "reason": "very sure", "cites": []}, profile=_RECORD_PROFILE)
    assert r.skeptic_verdict == "downgraded_overconfident"
    assert 0.5 < r.p_yes < 0.97  # pulled halfway toward the 0.5 prior


def test_deterministic_claims_monotonic_in_staff_signal():
    """The degraded Reasoner scores rise with the staff signal."""
    application = {
        "height_m": 40,
        "total_units": 100,
        "affordable_units": 10,
        "retail_sqft": 0,
        "requested_variances": ["h"],
    }
    profiles = {"a": _RECORD_PROFILE | {"councillor_id": "a"}}
    approve = panel.deterministic_claims(application, ["a"], profiles, 1.0, None, 0.0)["a"]["p_yes"]
    refuse = panel.deterministic_claims(application, ["a"], profiles, -1.0, None, 0.0)["a"]["p_yes"]
    assert approve > refuse


def test_run_panel_offline_produces_aligned_trace():
    """Offline, run_panel returns one trace per councillor with grounded/abstained counts."""
    application = {
        "height_m": 40,
        "total_units": 100,
        "affordable_units": 10,
        "retail_sqft": 0,
        "requested_variances": [],
    }
    profiles = {"a": _RECORD_PROFILE | {"councillor_id": "a"}}
    out = panel.run_panel(
        application, ["a", "b"], profiles, "approve", 1.0, [], None, use_llm=False
    )
    assert out.mode == "fallback"
    assert {t.councillor_id for t in out.traces} == {"a", "b"}
    assert sum(1 for t in out.traces if t.grounded) == 1  # 'a' grounded, 'b' abstains
