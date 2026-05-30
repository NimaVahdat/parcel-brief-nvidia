"""generate() — the contract function. Stub until retrieval + LLM are wired in."""

from opposition_generator.schemas import Letter, OppositionForecast, ProjectDescription


def generate(project: ProjectDescription, neighborhood: str) -> OppositionForecast:
    """Forecast community opposition for a Toronto development project.

    Mock implementation. Replace with:
      1. retrieve.top_k_deputations(neighborhood, project) → list of past letters
      2. LLM call with retrieved letters as in-context examples to generate
         neighborhood-voiced output for the current project
      3. aggregate top concerns from retrieved letters
      4. identify named organized groups from retrieved metadata
    """
    sample_letter = Letter(
        text=(
            f"As a long-time resident of {neighborhood}, I am writing to oppose the "
            f"proposed {project.height_m:.0f}m development. The shadow study will "
            f"clearly show significant impact on our public spaces, and the lack of "
            f"affordable units fails to address the community's needs."
        ),
        inferred_concerns=["shadow", "affordability", "character"],
        source_neighborhood=neighborhood,
    )

    return OppositionForecast(
        expected_letter_count=40,
        sample_letters=[sample_letter],
        top_concerns={
            "shadow": 0.78,
            "affordability": 0.65,
            "traffic": 0.40,
            "character": 0.32,
        },
        organized_groups=[f"{neighborhood} Residents Association"],
        mitigations=[
            "include a 600 sqft publicly-accessible community room",
            "add 12 affordable units",
            "preserve mature trees on the site",
        ],
    )
