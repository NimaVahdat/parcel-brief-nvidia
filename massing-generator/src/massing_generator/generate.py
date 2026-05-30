"""generate() — the contract function. Stub until the SDXL pipeline is wired."""

from massing_generator.schemas import Massing, MassingOutput, ZoningEnvelope


def generate(envelope: ZoningEnvelope) -> MassingOutput:
    """Generate viable 3D building massings for a zoning envelope.

    Mock implementation. Replace with:
      1. controlnet.build_mesh(envelope) → trimesh.Mesh
      2. controlnet.generate_facades(envelope) → list of generated images
      3. Apply facades as textures, export .glb
      4. Return MassingOutput with three URI options
    """
    base_height = envelope.max_height_m
    base_gfa = envelope.max_fsi * 1500  # placeholder lot area

    options = [
        Massing(
            massing_id=f"{envelope.parcel_id}-tall",
            height_m=base_height,
            total_gfa_m2=base_gfa,
            unit_mix={"studio": 12, "1br": 30, "2br": 28, "3br": 14},
            retail_sqft=2400,
            affordable_units=0,
            three_d_uri=f"mock://massing/{envelope.parcel_id}-tall.glb",
            facade_renders=[f"mock://render/{envelope.parcel_id}-tall-n.png"],
        ),
        Massing(
            massing_id=f"{envelope.parcel_id}-affordable",
            height_m=base_height,
            total_gfa_m2=base_gfa,
            unit_mix={"studio": 16, "1br": 32, "2br": 24, "3br": 12},
            retail_sqft=2400,
            affordable_units=12,
            three_d_uri=f"mock://massing/{envelope.parcel_id}-affordable.glb",
            facade_renders=[f"mock://render/{envelope.parcel_id}-affordable-n.png"],
        ),
        Massing(
            massing_id=f"{envelope.parcel_id}-conservative",
            height_m=base_height * 0.75,
            total_gfa_m2=base_gfa * 0.75,
            unit_mix={"1br": 24, "2br": 20, "3br": 10},
            retail_sqft=1800,
            affordable_units=6,
            three_d_uri=f"mock://massing/{envelope.parcel_id}-conservative.glb",
            facade_renders=[f"mock://render/{envelope.parcel_id}-conservative-n.png"],
        ),
    ]
    return MassingOutput(options=options)
