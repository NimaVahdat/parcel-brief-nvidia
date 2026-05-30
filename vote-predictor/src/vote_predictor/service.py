"""Optional standalone FastAPI service. Lets you demo this component in isolation.

The ``/predict`` response carries the Contract-1 ``VotePrediction`` fields plus an **additive**
``agent_trace`` field (the per-councillor reasoning and Skeptic verdicts). The extra field is
optional and non-breaking: Contract-1 consumers ignore it; the UI drill-down consumes it.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette.requests import Request

from vote_predictor.infer import predict_with_trace
from vote_predictor.schemas import AgentTrace, ApplicationFeatures, VotePrediction

logger = logging.getLogger(__name__)

app = FastAPI(title="vote-predictor", version="0.1.0")
# The UI dev server may hit this service directly during demos/debugging (the connector calls
# it server-side and is unaffected by CORS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class PredictRequest(ApplicationFeatures):
    """Predict request: the Contract-1 application plus the committee councillor ids.

    Attributes:
        councillors (list[str]): The committee roster (1-50; bounds the LLM fan-out).
    """

    councillors: list[str] = Field(min_length=1, max_length=50)


class PredictionWithTrace(VotePrediction):
    """A ``VotePrediction`` with an additive, optional reasoning trace.

    Attributes:
        agent_trace (AgentTrace | None): The per-councillor panel trace; ``None`` if omitted.
    """

    agent_trace: AgentTrace | None = None


@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Return a clean 500 for unexpected errors instead of leaking a traceback.

    Args:
        request (Request): The incoming request.
        exc (Exception): The unhandled exception.

    Returns:
        JSONResponse: A 500 with a generic detail; the traceback is logged server-side.
    """
    logger.exception("Unhandled error in %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "prediction failed"})


@app.post(
    "/predict",
    response_model=PredictionWithTrace,
    response_model_exclude_none=True,
    responses={503: {"description": "prediction backend unavailable"}},
)
def predict_endpoint(req: PredictRequest) -> PredictionWithTrace:
    """Predict a council vote and return the prediction with its reasoning trace.

    Args:
        req (PredictRequest): The application features plus the committee councillor ids.

    Returns:
        PredictionWithTrace: The Contract-1 prediction fields plus the additive agent trace.

    Raises:
        HTTPException: 503 if the prediction backend (model/data) is unavailable.
    """
    # Rebuild the ApplicationFeatures view dynamically so new contract fields are not silently
    # dropped (PredictRequest IS-A ApplicationFeatures plus councillors).
    application = ApplicationFeatures.model_validate(req.model_dump(exclude={"councillors"}))
    try:
        prediction, trace = predict_with_trace(application, req.councillors)
    except (ConnectionError, OSError) as exc:
        raise HTTPException(status_code=503, detail="prediction backend unavailable") from exc
    return PredictionWithTrace(**prediction.model_dump(), agent_trace=trace)


@app.get("/health", response_model=dict[str, str])
def health() -> dict[str, str]:
    """Liveness probe.

    Returns:
        dict[str, str]: ``{"status": "ok"}``.
    """
    return {"status": "ok"}
