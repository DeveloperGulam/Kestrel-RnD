"""
Tests for cross-sheet contradictions, unapproved trial recommendations,
and incomplete trial handling.
"""

import pytest


def test_t05_stability_cross_sheet_contradiction(cross_sheet_auditor):
    """
    Verified finding: Trial T-05 is recorded as 'Pass' in Trials_TX_Softeners,
    but in Stability_Log (week 3, 45°C), it is explicitly recorded as
    phase_sep = 'Y' and appearance = 'separated'.
    """
    res = cross_sheet_auditor.audit_t05_stability_contradiction()
    assert res["contradiction_found"] is True
    assert res["trials_sheet_status"] == "Pass"
    # Find the week 3 record
    w3 = next(r for r in res["stability_log_records"] if str(r["week"]) == "3" and str(r["temp_c"]) == "45")
    assert w3["phase_sep"] == "Y"
    assert w3["appearance"] == "separated"


def test_t04_governance_unapproved_status(cross_sheet_auditor):
    """
    Verified finding: Trial T-04 is recommended for scale-up in Summary_Apr,
    but Trials_TX_Softeners shows approved_by is NULL / empty.
    The trial was never formally approved by the lab supervisor.
    """
    res = cross_sheet_auditor.audit_t04_governance_flags()
    assert res["trial_id"] == "T-04"
    assert res["is_unapproved"] is True
    assert res["approved_by"] is None


def test_t11_incomplete_trial_must_not_be_assumed_passed(cross_sheet_auditor):
    """
    Verified requirement: Do not invent missing safety or stability data,
    or assume missing measurements pass.
    Trial T-11 has stability_45c_4wk = 'In progress (week 2)', ph is NaN,
    and approved_by is NaN. It must be treated as incomplete.
    """
    res = cross_sheet_auditor.audit_t11_status()
    assert res["trial_id"] == "T-11"
    assert res["is_incomplete"] is True
    assert res["stability_status"] == "In progress (week 2)"
    assert res["ph_value"] is None
    assert res["approved_by"] is None
    assert res["lims_status"] == "Open"


def test_regulatory_notes_treated_as_unverified_source_data(cross_sheet_auditor):
    """
    Verified requirement: Treat regulatory notes as source data requiring verification,
    not as independently verified legal conclusions.
    """
    notes = cross_sheet_auditor.audit_regulatory_notes_cross_check()
    assert len(notes) > 0
    for note in notes:
        assert note["classification"] == "Source Data Reference (Requires Verification)"
