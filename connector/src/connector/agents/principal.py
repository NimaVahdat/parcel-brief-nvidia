"""Principal agent — synthesizes all sections into a go/no-go recommendation.

Unlike the earlier stub (IRR + approval only), this factors in the **community
response**: heavy predicted opposition tempers a borderline buy, and the
recommended changes merge the opposition mitigations with the vote-prediction
levers — the two sources of "what would improve the outcome."
"""

from connector.agents.state import BriefState
from connector.schemas.brief import GoNoGo

IRR_THRESHOLD = 0.12
APPROVAL_THRESHOLD = 0.6
HIGH_OPPOSITION = 50   # expected deputation letters that signal a serious fight


def principal_agent(state: BriefState) -> BriefState:
    fin = state["financial_model"]
    approval = state["approval_forecast"].approval_probability
    community = state["community_response"]
    irr = fin.irr_5y

    letters = community.expected_letter_count
    top_concern = next(iter(community.top_concerns), None)
    heavy_opposition = letters >= HIGH_OPPOSITION

    # base call on economics + approvability
    if irr >= IRR_THRESHOLD and approval >= APPROVAL_THRESHOLD:
        rec, confidence = "buy", min(0.95, 0.5 + irr + approval * 0.3)
    elif irr < IRR_THRESHOLD * 0.7 or approval < 0.35:
        rec, confidence = "pass", 0.7
    else:
        rec, confidence = "conditional", 0.55

    # community opposition tempers a buy into conditional
    if rec == "buy" and heavy_opposition:
        rec, confidence = "conditional", 0.6

    # recommended changes: merge opposition mitigations + vote levers
    changes = list(community.mitigations[:2])
    changes += [lv.change for lv in state["approval_forecast"].levers[:2]]
    changes_txt = ("; ".join(dict.fromkeys(changes))) if changes else "no clear levers"

    opp_txt = (
        f"~{letters} deputations expected"
        + (f" (top concern: {top_concern})" if top_concern else "")
    )
    rationale = {
        "buy": (
            f"IRR {irr:.1%} and predicted approval {approval:.0%} both clear the bar, "
            f"with manageable community response ({opp_txt}). Proceed with acquisition."
        ),
        "pass": (
            f"IRR ({irr:.1%}) and/or approval ({approval:.0%}) are too low to justify "
            f"acquisition; {opp_txt}."
        ),
        "conditional": (
            f"IRR {irr:.1%}, approval {approval:.0%}, {opp_txt}. "
            f"Borderline — recommended changes: {changes_txt}."
        ),
    }[rec]

    sensitivities = list(fin.sensitivities.keys())[:3]
    if heavy_opposition:
        sensitivities = ["community opposition"] + sensitivities[:2]

    return {
        "recommendation": GoNoGo(
            recommendation=rec,
            confidence=round(confidence, 2),
            dominant_sensitivities=sensitivities,
            rationale=rationale,
        )
    }
