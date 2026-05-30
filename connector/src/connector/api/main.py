"""FastAPI app entry point."""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from connector.api.routes.analyze import router as analyze_router, warmup


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the pipeline in the background so the first real request is fast:
    # loads the GIS layers and makes the LLM models resident (no cold start).
    threading.Thread(target=warmup, daemon=True).start()
    yield


app = FastAPI(
    title="parcel-brief",
    version="0.0.1",
    description="Toronto site pre-acquisition analysis system.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
