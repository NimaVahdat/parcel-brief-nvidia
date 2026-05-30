"""Community response agent — calls opposition_generator.generate."""

from opposition_generator import generate as generate_opposition
from opposition_generator.schemas import ProjectDescription

from connector.agents.state import BriefState
from connector.schemas.brief import OppositionForecast


def community_agent(state: BriefState) -> BriefState:
    massing = state["design_options"].options[0]

    project = ProjectDescription(
        height_m=massing.height_m,
        total_units=sum(massing.unit_mix.values()),
        affordable_units=massing.affordable_units,
        use_mix={"residential": 0.85, "retail": 0.15},
        character_notes=None,
    )

    forecast = generate_opposition(project, neighborhood="Trinity-Bellwoods")
    return {"community_response": OppositionForecast.model_validate(forecast.model_dump())}
