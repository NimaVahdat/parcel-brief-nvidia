"""LangGraph wiring for the seven agents with real parallel edges.

Flow:
    START → zoning, constraints (parallel)
    → massing → proforma
    → approvals, community (parallel)
    → principal → END
"""

from langgraph.graph import END, START, StateGraph

from connector.agents.approvals import approvals_agent
from connector.agents.community import community_agent
from connector.agents.constraints import constraints_agent
from connector.agents.massing import massing_agent
from connector.agents.principal import principal_agent
from connector.agents.proforma import proforma_agent
from connector.agents.state import BriefState
from connector.agents.zoning import zoning_agent


def build_graph() -> object:
    g = StateGraph(BriefState)

    g.add_node("zoning", zoning_agent)
    g.add_node("constraints", constraints_agent)
    g.add_node("massing", massing_agent)
    g.add_node("proforma", proforma_agent)
    g.add_node("approvals", approvals_agent)
    g.add_node("community", community_agent)
    g.add_node("principal", principal_agent)

    # Parallel fan-out from START
    g.add_edge(START, "zoning")
    g.add_edge(START, "constraints")

    # Both feed into massing
    g.add_edge("zoning", "massing")
    g.add_edge("constraints", "massing")

    # Linear: massing → proforma
    g.add_edge("massing", "proforma")

    # Parallel fan-out from proforma
    g.add_edge("proforma", "approvals")
    g.add_edge("proforma", "community")

    # Both feed into principal
    g.add_edge("approvals", "principal")
    g.add_edge("community", "principal")

    g.add_edge("principal", END)

    return g.compile()


_compiled = None


def get_graph() -> object:
    """Return a cached compiled graph."""
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled
