"""
Tests for schema validity, primary key uniqueness, and identifier integrity.
Cites exact worksheet names and record IDs.
"""

import pytest


def test_worksheet_inventory(sheets):
    """Verifies all 12 worksheets are loaded."""
    expected_sheets = [
        "Export_Info",
        "RM_Master",
        "Price_Feed",
        "Trials_TX_Softeners",
        "Trials_All_Projects",
        "Stability_Log",
        "Panel_Scores",
        "Customer_Requests",
        "Lab_Schedule",
        "Regulatory_Notes",
        "Summary_Apr",
        "Sheet3",
    ]
    assert list(sheets.keys()) == expected_sheets


def test_trials_all_projects_duplicate_lims_ids(integrity_auditor):
    """
    Verified finding: Trials_All_Projects has duplicate lims_id values:
    'L-2025-031' (rows 18 and 61) and 'L-2025-044' (rows 30 and 44).
    """
    dups = integrity_auditor.audit_duplicate_primary_keys()
    assert "Trials_All_Projects.lims_id" in dups
    duplicate_lims = set(dups["Trials_All_Projects.lims_id"])
    assert "L-2025-031" in duplicate_lims
    assert "L-2025-044" in duplicate_lims


def test_customer_requests_duplicate_id(integrity_auditor):
    """
    Verified finding: Customer_Requests has duplicate request_id 'CR-2026-117'
    reused across two completely different projects (Harbor Knits Textiles vs Sunvale Fabrics Paper).
    """
    cr_dups = integrity_auditor.audit_duplicate_customer_requests()
    assert len(cr_dups) == 1
    assert cr_dups[0]["request_id"] == "CR-2026-117"
    records = cr_dups[0]["records"]
    assert len(records) == 2
    customers = {r["customer"] for r in records}
    assert "Harbor Knits" in customers
    assert "Sunvale Fabrics" in customers


def test_trials_tx_softeners_duplicate_batch_code(integrity_auditor):
    """
    Verified finding: Trials_TX_Softeners has batch_code 'LT-2404-03'
    reused for both Trial T-07 and Trial T-08 despite different formulas, equipment, and chemists.
    """
    batch_dups = integrity_auditor.audit_duplicate_batch_codes()
    assert len(batch_dups) == 1
    assert batch_dups[0]["batch_code"] == "LT-2404-03"
    assert "T-07" in batch_dups[0]["trial_ids"]
    assert "T-08" in batch_dups[0]["trial_ids"]


def test_sheet3_is_unstructured_scratchpad(schema_inspector):
    """Verifies that Sheet3 is flagged as an unstructured/scratch sheet."""
    schemas = schema_inspector.audit_all_sheets()
    assert schemas["Sheet3"]["is_unstructured_or_scratch"] is True
    assert schemas["Sheet3"]["row_count"] == 6
