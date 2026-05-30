"""Optional standalone FastAPI service."""

from fastapi import FastAPI
from pydantic import BaseModel

from opposition_generator.generate import generate
from opposition_generator.schemas import OppositionForecast, ProjectDescription

app = FastAPI(title="opposition-generator", version="0.0.1")


class GenerateRequest(BaseModel):
    project: ProjectDescription
    neighborhood: str


@app.post("/generate", response_model=OppositionForecast)
def generate_endpoint(req: GenerateRequest) -> OppositionForecast:
    return generate(req.project, req.neighborhood)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
