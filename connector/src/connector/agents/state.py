"""BriefState — LangGraph shared state for the seven agents.

Each agent reads the fields it needs and writes back its dedicated field.
"""

from typing import TypedDict

from connector.schemas.brief import (
    FinancialModel,
    GoNoGo,
    MassingOutput,
    OppositionForecast,
    SiteConstraints,
    VotePrediction,
    ZoningEnvelope,
)


class BriefState(TypedDict, total=False):
    parcel_id: str

    # Populated by zoning + constraints agents
    site_fundamentals: ZoningEnvelope
    site_constraints: SiteConstraints

    # Populated by massing agent
    design_options: MassingOutput

    # Populated by proforma agent
    financial_model: FinancialModel

    # Populated by approvals + community agents
    approval_forecast: VotePrediction
    community_response: OppositionForecast

    # Populated by principal agent
    recommendation: GoNoGo
