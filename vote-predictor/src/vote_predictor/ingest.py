"""TMMIS scraping for applications and recorded votes.

TODO: implement with Playwright. TMMIS is Akamai-protected and 403s plain HTTP.

Output target schemas (write to ./data/ as parquet):
- applications: app_id, parcel_id, application_date, committee, height_m, total_units,
  affordable_units, retail_sqft, neighborhood, requested_variances (list[str])
- votes: vote_id, app_id, committee, recorded_vote (bool), councillor_id, vote
  ("yes"/"no"/"absent"), meeting_date
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def scrape_tmmis_applications(start_year: int = 2014, end_year: int = 2026) -> None:
    """Scrape TMMIS for development applications. Stub."""
    raise NotImplementedError("Implement with Playwright; see docs/DATA.md")


def scrape_tmmis_votes(start_year: int = 2014, end_year: int = 2026) -> None:
    """Scrape TMMIS for recorded per-councillor votes. Stub."""
    raise NotImplementedError("Implement with Playwright; see docs/DATA.md")


if __name__ == "__main__":
    print("Not implemented yet. See docs/DATA.md for TMMIS scraping notes.")
