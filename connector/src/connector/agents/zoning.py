"""Zoning agent — reads zoning envelope from site_proforma."""

from site_proforma import lookup as site_lookup

from connector.agents.state import BriefState
from connector.schemas.brief import ZoningEnvelope


def zoning_agent(state: BriefState) -> BriefState:
    site = site_lookup(state["parcel_id"])
    envelope = ZoningEnvelope.model_validate(site.zoning_envelope.model_dump())
    return {"site_fundamentals": envelope}
