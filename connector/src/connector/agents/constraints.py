"""Constraints agent — reads site constraints from site_proforma."""

from site_proforma import lookup as site_lookup

from connector.agents.state import BriefState
from connector.schemas.brief import SiteConstraints


def constraints_agent(state: BriefState) -> BriefState:
    site = site_lookup(state["parcel_id"])
    constraints = SiteConstraints.model_validate(site.constraints.model_dump())
    return {"site_constraints": constraints}
