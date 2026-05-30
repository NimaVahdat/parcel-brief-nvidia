"""opposition-generator — Toronto community-response forecasting."""

from opposition_generator.generate import generate
from opposition_generator.schemas import Letter, OppositionForecast, ProjectDescription

__all__ = ["generate", "ProjectDescription", "OppositionForecast", "Letter"]
