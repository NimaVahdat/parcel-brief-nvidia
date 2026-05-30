"""Committed synthetic precedent corpus for offline dev / tests.

Real precedents are scraped from TMMIS into data/precedents.jsonl (gitignored).
These samples mirror the shape and signal of real Toronto outcomes (affordable
housing and modest scale tend to pass; over-height + many variances tend to fail)
so retrieve -> predict -> eval all run without a scrape. `text` never contains the
outcome (no label leakage).
"""

from __future__ import annotations


def _p(pid, text, outcome, ward, app_type, year=2023):
    return {
        "precedent_id": pid, "text": text, "outcome": outcome, "ward": ward,
        "committee": "te", "year": year, "app_type": app_type, "address": "", "votes": {},
    }


SAMPLE_PRECEDENTS: list[dict] = [
    _p("seed-1", "Development application in Trinity-Bellwoods: 30 m, 60 units, 18 affordable units, residential and retail, mid-rise on a main street.", "approved", "10", "Zoning By-law Amendment"),
    _p("seed-2", "Development application in Trinity-Bellwoods: 45 m, 90 units, no affordable units, residential, exceeds avenue height with several variances.", "refused", "10", "Zoning By-law Amendment"),
    _p("seed-3", "Development application in The Annex: 28 m, 50 units, 12 affordable units, residential, gentle mid-rise near transit.", "approved", "11", "Official Plan Amendment"),
    _p("seed-4", "Development application in The Annex: 60 m, 150 units, no affordable units, residential, tower far above the planned context.", "refused", "11", "Zoning By-law Amendment"),
    _p("seed-5", "Development application in Leslieville: 24 m, 40 units, 10 affordable units, residential and retail, fits the avenue.", "approved", "14", "Site Plan Approval"),
    _p("seed-6", "Development application in Liberty Village: 38 m, 120 units, 6 affordable units, residential, near transit station.", "approved", "10", "Zoning By-law Amendment"),
    _p("seed-7", "Development application in Rosedale: 18 m, 12 units, no affordable units, residential, demolition of a heritage home with variances.", "refused", "11", "Committee of Adjustment"),
    _p("seed-8", "Development application in Summerhill: 50 m, 110 units, no affordable units, residential, over-height tower with multiple variances near low-rise homes.", "refused", "12", "Zoning By-law Amendment"),
    _p("seed-9", "Development application in Cabbagetown: 22 m, 30 units, 8 affordable units, residential, heritage-sensitive infill.", "approved", "13", "Official Plan Amendment"),
    _p("seed-10", "Development application in The Junction: 32 m, 70 units, 14 affordable units, residential and retail, transit-supportive mid-rise.", "approved", "9", "Zoning By-law Amendment"),
    _p("seed-11", "Development application in The Junction: 55 m, 140 units, no affordable units, residential, exceeds context with variances.", "refused", "9", "Zoning By-law Amendment"),
    _p("seed-12", "Development application in Davisville: 42 m, 100 units, 10 affordable units, residential, near subway, modest variances.", "approved", "12", "Site Plan Approval"),
    _p("seed-13", "Development application in Beaches-East York: 16 m, 18 units, no affordable units, residential, low-rise main street infill.", "approved", "19", "Committee of Adjustment"),
    _p("seed-14", "Development application in Beaches-East York: 35 m, 80 units, no affordable units, residential, over scale for a low-rise area.", "refused", "19", "Zoning By-law Amendment"),
    _p("seed-15", "Development application in Yonge-Eglinton: 70 m, 220 units, 22 affordable units, residential and retail, intensification at a major transit node.", "approved", "8", "Official Plan Amendment"),
    _p("seed-16", "Development application in Yonge-Eglinton: 90 m, 300 units, no affordable units, residential, tower with many variances overwhelming the intersection.", "refused", "8", "Zoning By-law Amendment"),
    _p("seed-17", "Development application in Corktown: 26 m, 45 units, 12 affordable units, residential and retail, fits the West Don Lands plan.", "approved", "13", "Site Plan Approval"),
    _p("seed-18", "Development application in St. Lawrence: 20 m, 35 units, 9 affordable units, residential, heritage-sensitive mid-rise.", "approved", "13", "Official Plan Amendment"),
    _p("seed-19", "Development application in Forest Hill: 24 m, 28 units, no affordable units, residential, exceeds neighbourhood scale with variances.", "refused", "8", "Committee of Adjustment"),
    _p("seed-20", "Development application in Danforth: 30 m, 65 units, 13 affordable units, residential and retail, transit-supportive on a main street.", "approved", "14", "Zoning By-law Amendment"),
    _p("seed-21", "Development application in Bloor West Village: 40 m, 95 units, no affordable units, residential, over-height for the avenue with variances.", "refused", "4", "Zoning By-law Amendment"),
    _p("seed-22", "Development application in Don Mills: 48 m, 130 units, 16 affordable units, residential and retail, intensification near a mobility hub.", "approved", "16", "Official Plan Amendment"),
    _p("seed-23", "Development application in Waterfront: 34 m, 85 units, 20 affordable units, residential, aligns with the precinct plan.", "approved", "10", "Site Plan Approval"),
    _p("seed-24", "Development application in Riverdale: 52 m, 125 units, no affordable units, residential, tower out of character with many variances.", "refused", "14", "Zoning By-law Amendment"),
]
