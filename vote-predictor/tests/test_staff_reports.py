"""Tests for the title-first staff-recommendation classifier (the D2 defect fix).

These encode the exact mislabels the Phase-0 adversarial pass found in the old whole-document
substring scanner: a clean Approval downgraded to approve_with_conditions by boilerplate
"conditions", and an approval flipped to refuse by OLT-appeal boilerplate.
"""

from __future__ import annotations

from vote_predictor import staff_reports

# A realistic decision-report body: approval of a rezoning that, like nearly every real
# rezoning, mentions a holding symbol, Section 37 community benefits, and the word
# "conditions" in boilerplate — none of which should downgrade the clean Approval.
_APPROVAL_BODY = """
Decision Report - Approval
Planning Application Number: 22 210125 STE 14 OZ
929 Queen Street East - Official Plan and Zoning By-law Amendment

RECOMMENDATIONS
The Director, Community Planning, Toronto and East York District recommends that:
1. City Council amend the Official Plan, substantially in accordance with the draft.
2. City Council amend Zoning By-law 569-2013 with a holding symbol (H).
3. Pursuant to Section 37, the owner shall provide community benefits.
Should Council refuse the application, the applicant may appeal to the Ontario Land Tribunal.
Standard conditions of site plan approval will apply at a later stage.
"""

_REFUSAL_BODY = """
Decision Report - Refusal
Planning Application Number: 23 998877 NNY 08 OZ
100 Tall Tower Road - Zoning By-law Amendment

RECOMMENDATIONS
The Director, Community Planning, North York District recommends that:
1. City Council refuse the application for the reasons set out in this report.
"""

_PRELIMINARY_BODY = """
Preliminary Report
Planning Application Number: 24 111222 ESC 21 SA
5 Future Lane - Site Plan Control

This preliminary report provides information and seeks direction. No recommendation on the
merits is made at this stage.
"""


def test_approval_with_section37_boilerplate_is_approve_not_conditions():
    """A clean Approval is not downgraded by Section 37 / holding / boilerplate 'conditions'."""
    title = staff_reports.extract_title(_APPROVAL_BODY)
    assert staff_reports.classify_recommendation(title, _APPROVAL_BODY) == "approve"


def test_olt_appeal_boilerplate_does_not_flip_approval_to_refuse():
    """'should Council refuse ... may appeal' boilerplate must not classify as refuse."""
    result = staff_reports.classify_recommendation("Decision Report - Approval", _APPROVAL_BODY)
    assert result == "approve"


def test_refusal_report_classifies_as_refuse():
    """A genuine refusal recommendation is classified as refuse."""
    title = staff_reports.extract_title(_REFUSAL_BODY)
    assert staff_reports.classify_recommendation(title, _REFUSAL_BODY) == "refuse"


def test_explicit_conditional_approval_is_conditions():
    """Explicit 'approve, subject to the conditions' yields approve_with_conditions."""
    body = "RECOMMENDATIONS\nCity Council approve the application, subject to the conditions in Attachment 5."
    assert (
        staff_reports.classify_recommendation("Final Report - Approval", body)
        == "approve_with_conditions"
    )


def test_preliminary_report_returns_none():
    """A Preliminary report predates the verdict and yields no staff_recs row."""
    assert (
        staff_reports.parse_report_type(staff_reports.extract_title(_PRELIMINARY_BODY))
        == "preliminary"
    )
    row = staff_reports.parse_staff_report(b"unused", "http://x", None)  # image-only path
    assert row is None  # empty text -> abstain


def test_extract_application_number_matches_aic_format():
    """The Planning Application Number is extracted and normalized to the AIC format."""
    assert staff_reports.extract_application_number(_APPROVAL_BODY) == "22 210125 STE 14 OZ"


def test_district_alias_normalizes_to_aic_form():
    """A historical district code (TEY) is normalized so it matches the AIC datastore (STE)."""
    text = "Planning Application Number: 22 210125 TEY 14 OZ"
    assert staff_reports.extract_application_number(text) == "22 210125 STE 14 OZ"
