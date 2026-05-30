"""Pro-forma agent — calls site_proforma.calculate with massing + site."""

from site_proforma import calculate as calculate_proforma
from site_proforma.schemas import Massing as SiteMassing
from site_proforma.schemas import SiteData as SiteSiteData

from connector.agents.state import BriefState
from connector.schemas.brief import FinancialModel


def proforma_agent(state: BriefState) -> BriefState:
    massing = state["design_options"].options[0]
    envelope = state["site_fundamentals"]
    constraints = state["site_constraints"]

    site_data = SiteSiteData.model_validate(
        {
            "zoning_envelope": envelope.model_dump(),
            "constraints": constraints.model_dump(),
        }
    )
    site_massing = SiteMassing.model_validate(massing.model_dump())

    model = calculate_proforma(site_massing, site_data)
    return {"financial_model": FinancialModel.model_validate(model.model_dump())}
