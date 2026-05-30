"""StatsCan 2021 Census tract ingestion.

Source: https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/index-eng.cfm

Useful for demographic context: median income, population density, housing
tenure. Joined to parcels via census tract.
"""


def ingest() -> None:
    """Pull StatsCan census-tract data for Toronto CMA (code 535) into Postgres."""
    raise NotImplementedError("Implement census-tract download + load.")


if __name__ == "__main__":
    ingest()
