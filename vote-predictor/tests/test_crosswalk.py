"""Tests for the crosswalk — the D1 fix: real data must actually join.

Covers the exact application-number bridge, the fuzzy address+committee+date fallback, the
uniqueness guard, and the regression that proves a real (non-synthetic) votes/apps merge is
non-empty after the crosswalk is applied.
"""

from __future__ import annotations

import pandas as pd
from vote_predictor import crosswalk

_APPS = pd.DataFrame(
    [
        {
            "application_id": "22 210125 STE 14 OZ",
            "committee": "toronto-east-york",
            "address": "929 QUEEN ST E",
            "application_date": "2023-01-15",
        },
        {
            "application_id": "23 555444 NNY 08 OZ",
            "committee": "north-york",
            "address": "100 TALL TOWER RD",
            "application_date": "2023-02-01",
        },
    ]
)

# Staff rec bridges the first app to a TMMIS item by exact application number.
_STAFF = pd.DataFrame(
    [
        {
            "application_id": "22 210125 STE 14 OZ",
            "agenda_item_id": "2024.TE12.5",
            "report_uri": "https://www.toronto.ca/legdocs/mmis/2024/te/bgrd/backgroundfile-242833.pdf",
        }
    ]
)

# Two vote items: one matches the staff bridge (exact), one only has a title address (fuzzy).
_VOTES = pd.DataFrame(
    [
        {
            "agenda_item_id": "2024.TE12.5",
            "item_title": "929 Queen Street East - Official Plan Amendment",
            "committee": "toronto-east-york",
            "meeting_date": "2024-05-10",
            "councillor_id": "perks",
            "vote": "Yes",
        },
        {
            "agenda_item_id": "2024.NY8.3",
            "item_title": "100 Tall Tower Road - Zoning By-law Amendment",
            "committee": "north-york",
            "meeting_date": "2024-03-01",
            "councillor_id": "carmichael",
            "vote": "No",
        },
    ]
)


def test_exact_and_fuzzy_links_built():
    """Both an exact application-number link and a fuzzy address link are produced."""
    xwalk = crosswalk.build_crosswalk(_APPS, _STAFF, _VOTES)
    methods = dict(zip(xwalk["agenda_item_id"], xwalk["join_method"], strict=False))
    assert methods["2024.TE12.5"] == "exact_appnum"
    assert methods["2024.NY8.3"] == "address_ward_date"


def test_apply_crosswalk_enables_real_merge():
    """After applying the crosswalk, votes carry application_id and the merge is non-empty (D1)."""
    xwalk = crosswalk.build_crosswalk(_APPS, _STAFF, _VOTES)
    apps2, votes2 = crosswalk.apply_crosswalk(_APPS, _VOTES, xwalk)
    merged = votes2.dropna(subset=["application_id"]).merge(apps2, on="application_id")
    assert len(merged) == 2  # both votes joined to their applications
    assert set(votes2["join_confidence"].dropna()) <= {"high", "medium", "low"}


def test_coverage_report():
    """Coverage reflects the fraction of applications linked to a recorded vote."""
    xwalk = crosswalk.build_crosswalk(_APPS, _STAFF, _VOTES)
    report = crosswalk.coverage_report(_APPS, xwalk)
    assert report["n_applications"] == 2
    assert report["n_linked"] == 2
    assert report["coverage"] == 1.0


def test_fuzzy_skipped_when_ambiguous():
    """A title that matches two same-committee addresses equally is left unlinked (abstain)."""
    apps = pd.DataFrame(
        [
            {
                "application_id": "A",
                "committee": "toronto-east-york",
                "address": "10 KING ST W",
                "application_date": "2023-01-01",
            },
            {
                "application_id": "B",
                "committee": "toronto-east-york",
                "address": "10 KING ST W",
                "application_date": "2023-01-01",
            },
        ]
    )
    votes = pd.DataFrame(
        [
            {
                "agenda_item_id": "2024.TE1.1",
                "item_title": "10 King Street West - Rezoning",
                "committee": "toronto-east-york",
                "meeting_date": "2024-01-01",
            }
        ]
    )
    xwalk = crosswalk.build_crosswalk(apps, None, votes)
    assert xwalk.empty  # ambiguous -> no link
