"""lookup() — the contract function for site data."""

from site_proforma.schemas import SiteConstraints, SiteData, ZoningEnvelope


def lookup(parcel_id: str) -> SiteData:
    """Look up zoning envelope + site constraints for a Toronto parcel.

    Mock implementation. Replace with PostGIS spatial joins:
      1. SELECT zoning columns WHERE ST_Within(parcel.geom, zoning.geom).
      2. LEFT JOIN heritage_register on parcel_id.
      3. LEFT JOIN trees WHERE ST_DWithin(parcel.geom, tree.geom, 30).
      4. LEFT JOIN trca_regulated_area WHERE ST_Intersects(parcel.geom, trca.geom).
      5. transit_distance = ST_Distance(parcel.geom, nearest TTC stop).
      6. Apply sun-shadow rules based on height + neighborhood proximity to parks.
    """
    envelope = ZoningEnvelope(
        parcel_id=parcel_id,
        max_height_m=42.0,
        max_fsi=4.0,
        setbacks={"north": 3.0, "south": 0.0, "east": 1.5, "west": 1.5},
        permitted_uses=["residential", "retail", "office"],
        footprint_polygon=[
            (-79.418, 43.649),
            (-79.418, 43.650),
            (-79.417, 43.650),
            (-79.417, 43.649),
            (-79.418, 43.649),
        ],
        parking_minimum=0,
    )
    constraints = SiteConstraints(
        parcel_id=parcel_id,
        heritage_status="listed",
        tree_canopy_area_m2=42.0,
        sun_shadow_rules=["5h equinox sun on Trinity Bellwoods Park north sidewalk"],
        conservation_overlays=[],
        transit_distance_m=180.0,
        easements=[],
    )
    return SiteData(zoning_envelope=envelope, constraints=constraints)
