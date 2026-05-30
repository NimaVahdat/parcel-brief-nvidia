"""Orchestrator API.

  POST /analyze          -> runs the pipeline, returns the brief (cached by parcel_id)
  GET  /analyze/stream   -> Server-Sent Events: one event per agent as it *actually*
                            completes (real progress), then the final brief

Results are cached by parcel_id, so a refresh (or a repeat click) returns instantly.
A per-parcel lock dedupes concurrent identical requests.
"""

from __future__ import annotations

import json
import threading

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from connector.agents.graph import get_graph
from connector.schemas.brief import AnalyzeRequest, BriefResponse

router = APIRouter()

# parcel_id -> BriefResponse.model_dump() ; survives for the life of the process
_CACHE: dict[str, dict] = {}
_LOCKS: dict[str, threading.Lock] = {}
_CACHE_LOCK = threading.Lock()

# graph node order, surfaced to the UI as real progress steps
_NODE_ORDER = ["zoning", "constraints", "massing", "proforma", "approvals", "community", "principal"]

# a real downtown lot used to warm the whole pipeline (models + GIS) on startup
WARMUP_PARCEL = "43.6563_-79.3809"


def _lock_for(parcel_id: str) -> threading.Lock:
    with _CACHE_LOCK:
        return _LOCKS.setdefault(parcel_id, threading.Lock())


def _assemble(parcel_id: str, state: dict) -> BriefResponse:
    return BriefResponse(
        parcel_id=parcel_id,
        site_fundamentals=state["site_fundamentals"],
        site_constraints=state["site_constraints"],
        design_options=state["design_options"],
        financial_model=state["financial_model"],
        approval_forecast=state["approval_forecast"],
        community_response=state["community_response"],
        recommendation=state["recommendation"],
    )


def _run(parcel_id: str) -> dict:
    """Run the pipeline (or return cache). Returns the BriefResponse dump."""
    if parcel_id in _CACHE:
        return _CACHE[parcel_id]
    with _lock_for(parcel_id):
        if parcel_id in _CACHE:
            return _CACHE[parcel_id]
        state = get_graph().invoke({"parcel_id": parcel_id})
        brief = _assemble(parcel_id, state).model_dump()
        _CACHE[parcel_id] = brief
        return brief


def warmup() -> None:
    """Warm the whole pipeline (load GIS layers, resident LLM models) on startup."""
    try:
        _run(WARMUP_PARCEL)
    except Exception:  # never let warm-up crash the server
        pass


@router.post("/analyze", response_model=BriefResponse)
def analyze(req: AnalyzeRequest) -> BriefResponse:
    try:
        return BriefResponse(**_run(req.parcel_id))
    except KeyError as e:
        raise HTTPException(status_code=500, detail=f"missing field: {e}") from e


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@router.get("/analyze/stream")
def analyze_stream(parcel_id: str) -> StreamingResponse:
    def gen():
        # cache hit -> flash all steps complete, then the brief (instant refresh)
        if parcel_id in _CACHE:
            for node in _NODE_ORDER:
                yield _sse({"agent": node})
            yield _sse({"brief": _CACHE[parcel_id], "cached": True})
            return

        lock = _lock_for(parcel_id)
        with lock:
            if parcel_id in _CACHE:
                for node in _NODE_ORDER:
                    yield _sse({"agent": node})
                yield _sse({"brief": _CACHE[parcel_id], "cached": True})
                return
            accumulated: dict = {"parcel_id": parcel_id}
            try:
                for update in get_graph().stream({"parcel_id": parcel_id}, stream_mode="updates"):
                    for node, delta in update.items():
                        if delta:
                            accumulated.update(delta)
                        yield _sse({"agent": node})
                brief = _assemble(parcel_id, accumulated).model_dump()
                _CACHE[parcel_id] = brief
                yield _sse({"brief": brief})
            except Exception as e:  # surface failures to the client
                yield _sse({"error": str(e)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
