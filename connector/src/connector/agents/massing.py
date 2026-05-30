"""Massing agent — calls massing_generator with the zoning envelope."""

from massing_generator import generate as generate_massing
from massing_generator.schemas import ZoningEnvelope as MassingZoningEnvelope

from connector.agents.state import BriefState
from connector.schemas.brief import Massing, MassingOutput


def massing_agent(state: BriefState) -> BriefState:
    envelope = state["site_fundamentals"]
    massing_envelope = MassingZoningEnvelope.model_validate(envelope.model_dump())
    output = generate_massing(massing_envelope)

    options = [Massing.model_validate(m.model_dump()) for m in output.options]
    return {"design_options": MassingOutput(options=options)}
