"""FastAPI app entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from massing_generator.builder.paths import OUTPUT_DIR, ensure_dirs

from connector.api.routes.analyze import router as analyze_router
from connector.api.routes.massing import router as massing_router

app = FastAPI(
    title="parcel-brief",
    version="0.0.1",
    description="Toronto site pre-acquisition analysis system.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router)
app.include_router(massing_router)

# Serve the massing 3D render artifacts (self-contained HTML, glTF, PNG).
ensure_dirs()
app.mount("/renders", StaticFiles(directory=str(OUTPUT_DIR)), name="renders")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
