"""POST /massing/{massing_id}/render — return a 3D HTML view for a design option.

Picks one of the pre-rendered building HTML files in ``OUTPUT_DIR``
(massing-generator/data/renders) and returns its URL, served statically under
``/renders``. The choice is seeded by ``massing_id`` so each option gets a
stable but distinct building across re-selects.
"""

import random

from fastapi import APIRouter, HTTPException
from massing_generator.builder.paths import OUTPUT_DIR

router = APIRouter()


@router.post("/massing/{massing_id}/render")
def render_massing(massing_id: str, glb: bool = True, force: bool = False) -> dict[str, str]:
    htmls = sorted(p.name for p in OUTPUT_DIR.glob("*.html"))
    if not htmls:
        raise HTTPException(status_code=404, detail="No rendered HTML available")

    # Seed by massing_id → same option always maps to the same building.
    choice = random.Random(massing_id).choice(htmls)
    return {"html_url": f"/renders/{choice}"}
