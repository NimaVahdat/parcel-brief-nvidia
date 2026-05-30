"""SDXL + ControlNet facade pipeline and envelope-to-mesh geometry.

Two responsibilities:

1. Deterministic geometry: footprint polygon + height + setbacks → trimesh.Mesh.
   Use shapely.Polygon for the footprint, apply setbacks with .buffer(-d),
   then trimesh.creation.extrude_polygon for the mass.

2. Generative: SDXL with a Canny ControlNet conditioned on the elevation outline
   of each face. Prompt with use mix + Toronto vernacular descriptors. Apply
   optional LoRA loaded from lora.py.
"""


def build_mesh(envelope: dict) -> object:
    """Build the deterministic 3D mass from the envelope. Returns a trimesh.Mesh.

    TODO: import shapely, trimesh; convert footprint to local meters; apply
    setbacks via buffer; extrude to max_height_m.
    """
    raise NotImplementedError("Envelope → mesh geometry not implemented.")


def generate_facades(envelope: dict, mesh: object) -> list:
    """Generate one facade image per visible face using SDXL + Canny ControlNet.

    TODO: import diffusers.StableDiffusionXLControlNetPipeline; for each face,
    rasterize the silhouette to a Canny edge image; condition SDXL with that
    edge image plus a text prompt; return list[PIL.Image].
    """
    raise NotImplementedError("SDXL + ControlNet pipeline not implemented.")
