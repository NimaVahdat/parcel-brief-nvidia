"""Tests for the TMMIS vote parsers (the D4 defect fix: pick the main disposition motion)."""

from __future__ import annotations

from vote_predictor import tmmis_source

# A Member Voting Record CSV with TWO recorded motions on one item: an amendment, then the
# main 'Adopt the item' disposition. The label must come from the main motion, not the
# amendment (the old tables[0] path grabbed whichever came first).
_CSV = """Agenda Item #,Agenda Item Title,Motion Type,Member,Vote,Result,Date
2024.TE12.5,929 Queen Street East - Rezoning,Motion to Amend,Gord Perks,No,Lost,2024-05-10
2024.TE12.5,929 Queen Street East - Rezoning,Motion to Amend,Paula Fletcher,Yes,Lost,2024-05-10
2024.TE12.5,929 Queen Street East - Rezoning,Adopt the item,Gord Perks,Yes,Carried,2024-05-10
2024.TE12.5,929 Queen Street East - Rezoning,Adopt the item,Paula Fletcher,Yes,Carried,2024-05-10
"""

_MIRROR_HTML = """
<html><body>
<h1>2025.EX22.4 - 2025 Education Property Tax Levy</h1>
<h3>Yes Votes (2)</h3>
<ul><li>Olivia Chow (Ward 0)</li><li>Gord Perks (Ward 4)</li></ul>
<h3>No Votes (1)</h3>
<ul><li>Stephen Holyday (Ward 2)</li></ul>
</body></html>
"""


def test_main_disposition_motion_is_selected():
    """Each member gets exactly one vote per item — their vote on the main motion."""
    votes = tmmis_source.parse_member_vote_csv(_CSV)
    assert len(votes) == 2  # two members, one disposition vote each
    assert set(votes["motion"]) == {"Adopt the item"}
    perks = votes[votes["councillor_id"] == "perks"].iloc[0]
    assert perks["vote"] == "Yes"  # main motion, not the amendment 'No'


def test_committee_derived_from_item_id():
    """The committee slug is derived from the agenda item id body code (TE -> toronto-east-york)."""
    votes = tmmis_source.parse_member_vote_csv(_CSV)
    assert set(votes["committee"]) == {"toronto-east-york"}
    assert set(votes["agenda_item_id"]) == {"2024.TE12.5"}


def test_councillor_ids_normalized():
    """Member names are normalized to surname slugs that match the model's id space."""
    votes = tmmis_source.parse_member_vote_csv(_CSV)
    assert set(votes["councillor_id"]) == {"perks", "fletcher"}


def test_mirror_roster_parsed():
    """The mirror's Yes/No rosters parse into one vote row per member, with the right side."""
    votes = tmmis_source.parse_mirror_item(_MIRROR_HTML, "2025.EX22.4")
    by_id = {r["councillor_id"]: r["vote"] for r in votes.to_dict("records")}
    assert by_id.get("chow") == "Yes"
    assert by_id.get("perks") == "Yes"
    assert by_id.get("holyday") == "No"
    assert set(votes["committee"]) == {"executive"}
