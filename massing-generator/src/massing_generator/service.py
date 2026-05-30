"""Optional standalone FastAPI service."""

from fastapi import FastAPI

from massing_generator.generate import generate
from massing_generator.schemas import MassingOutput, ZoningEnvelope

app = FastAPI(title="massing-generator", version="0.0.1")


@app.post("/generate", response_model=MassingOutput)
def generate_endpoint(envelope: ZoningEnvelope) -> MassingOutput:
    return generate(envelope)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
