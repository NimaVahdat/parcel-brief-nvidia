"""Principal agent — synthesizes the six sections into a go/no-go recommendation."""

from connector.agents.state import BriefState
from connector.schemas.brief import GoNoGo


# TODO: replace this rule-based stub with a small LLM call that synthesizes the
# rationale in natural language using all six sections.

IRR_THRESHOLD = 0.12
APPROVAL_THRESHOLD = 0.6


def principal_agent(state: BriefState) -> BriefState:
    irr = state["financial_model"].irr_5y
    approval = state["approval_forecast"].approval_probability

    if irr >= IRR_THRESHOLD and approval >= APPROVAL_THRESHOLD:
        rec = "buy"
        confidence = min(0.95, 0.5 + irr + approval * 0.3)
        rationale = (
            f"IRR of {irr:.1%} exceeds threshold and predicted approval probability "
            f"of {approval:.0%} clears the bar. Proceed with site acquisition."
        )
    elif irr < IRR_THRESHOLD * 0.7 or approval < 0.35:
        rec = "pass"
        confidence = 0.7
        rationale = (
            f"IRR ({irr:.1%}) and/or approval probability ({approval:.0%}) are too "
            f"low to justify acquisition under current parameters."
        )
    else:
        rec = "conditional"
        confidence = 0.55
        rationale = (
            f"IRR ({irr:.1%}) and approval probability ({approval:.0%}) are borderline. "
            f"Apply the recommended levers from the approval forecast and re-evaluate."
        )

    sensitivities = list(state["financial_model"].sensitivities.keys())[:3]
    return {
        "recommendation": GoNoGo(
            recommendation=rec,
            confidence=confidence,
            dominant_sensitivities=sensitivities,
            rationale=rationale,
        )
    }
