"""
Tests for unit of measure inconsistencies, scale variations, and date/chronology anomalies.
"""

import pytest


def test_trial_t04_viscosity_unit_mismatch_and_exceeds_target(unit_date_auditor):
    """
    Verified finding: Trial T-04 has viscosity recorded as '0.45 Pa·s' instead of 'cP'.
    Normalized to cP, this is 450 cP, which violates the customer target brief (50–300 cP).
    """
    findings = {f["trial_id"]: f for f in unit_date_auditor.audit_viscosity_units()}
    assert "T-04" in findings
    t04 = findings["T-04"]
    assert t04["is_non_standard_unit"] is True
    assert t04["unit_detected"] == "Pa·s"
    assert t04["normalized_cP"] == 450.0
    assert t04["exceeds_customer_target"] is True


def test_softness_scale_inconsistency_trial_t06(unit_date_auditor):
    """
    Verified finding: Trial T-06 softness was recorded on a 1-10 scale ('8/10'),
    while all other trials in Trials_TX_Softeners were recorded on a 1-5 scale.
    """
    scales = unit_date_auditor.audit_softness_scales()
    tx_scales = {s["trial_id"]: s for s in scales["tx_softeners_scales"]}
    assert "T-06" in tx_scales
    assert tx_scales["T-06"]["scale_denominator"] == "10"
    assert tx_scales["T-06"]["is_non_standard_scale"] is True

    # Check panel scores scale
    assert "T-06" in scales["panel_scores_scales"]["trials_on_10_scale"]


def test_rm170_drum_uom_packaging(unit_date_auditor):
    """
    Verified finding: RM-170 in RM_Master uses UOM 'drum (200 kg)' with price 32000 INR.
    Direct ingestion without packaging normalization creates a 200x costing error.
    """
    findings = unit_date_auditor.audit_uom_packaging()
    rm170_uom = next((f for f in findings if f["code"] == "RM-170"), None)
    assert rm170_uom is not None
    assert rm170_uom["uom"] == "drum (200 kg)"
    assert rm170_uom["list_price"] == 32000.0


def test_trial_t12_stability_chronological_impossibility(unit_date_auditor):
    """
    Verified finding: Trial T-12 was formulated on 2026-05-13.
    The export was generated on 2026-05-20 (7 days later).
    Yet Stability_Log contains Week 2, Week 3, and Week 4 test results for T-12.
    """
    anomalies = unit_date_auditor.audit_chronological_anomalies()
    t12_anomaly = next((a for a in anomalies if a.get("sample_id") == "T-12"), None)
    assert t12_anomaly is not None
    assert 4 in t12_anomaly["weeks_logged"] or "4" in t12_anomaly["weeks_logged"]


def test_lab_schedule_future_completed_bookings(unit_date_auditor):
    """
    Verified finding: Lab_Schedule has bookings with dates AFTER the export date
    (e.g., 2026-05-21, 2026-05-27) that are already marked 'Completed'.
    """
    anomalies = unit_date_auditor.audit_chronological_anomalies()
    future_completed = [a for a in anomalies if a.get("entity") == "Lab_Schedule"]
    assert len(future_completed) >= 1
    booking_ids = {b["booking_id"] for b in future_completed}
    assert "BK-2601" in booking_ids
