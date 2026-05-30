"""CMHC Rental Market Survey ingestion.

Source: https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/housing-data/data-tables/rental-market/rental-market-report-data-tables

Target schema:
    cmhc_rents (
        neighborhood TEXT,         -- CMHC "zone" or sub-area
        bedroom_count INTEGER,
        avg_rent_monthly NUMERIC,
        vacancy_rate NUMERIC,
        year INTEGER
    )
"""


def ingest() -> None:
    """Parse CMHC rental survey XLSX → Postgres."""
    raise NotImplementedError(
        "Download Toronto CMA zone-level tables, parse with openpyxl, INSERT."
    )


if __name__ == "__main__":
    ingest()
