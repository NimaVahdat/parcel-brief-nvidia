"""Building photo collection for the LoRA dataset.

Stub. Owner decides the approach (Street View API, Wikimedia scrape, manual curation).
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "training_images"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def collect_toronto_building_photos() -> None:
    """Download a curated set of Toronto building photos for the LoRA.

    TODO: pick a source (Wikimedia Commons API is the cleanest license-wise),
    download ~200 high-quality images of mid-rise / mixed-use buildings,
    write captions next to each file.
    """
    raise NotImplementedError("Photo collection not implemented.")
