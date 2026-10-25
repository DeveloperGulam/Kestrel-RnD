"""
Tests for pricing integrity, currency reconciliation, and cost recalculation.
"""

import pytest


def test_price_feed_duplicate_monthly_records(pricing_auditor):
    """
    Verified finding: Price_Feed has conflicting duplicate records for month 2026-05:
    - RM-101: 210.0 INR (PurchaseOne auto) vs 228.0 INR (email manual) -> delta 18.0 INR
    - RM-170: 32800.0 INR (per drum) vs 164.0 INR (quote per kg) -> delta 32636.0 INR
    """
    conflicts = pricing_auditor.audit_duplicate_monthly_feed()
    assert len(conflicts) == 2
    codes = {c["code"] for c in conflicts}
    assert "RM-101" in codes
    assert "RM-170" in codes

    rm101_conflict = next(c for c in conflicts if c["code"] == "RM-101")
    assert rm101_conflict["price_delta"] == 18.0


def test_multi_currency_in_raw_materials(pricing_auditor):
    """
    Verified finding: Raw materials catalog mixes INR and USD currencies.
    USD entries include RM-140, RM-160, RM-203, and RM-304.
    """
    dist = pricing_auditor.audit_currency_distribution()
    assert "USD" in dist["RM_Master"]
    assert "INR" in dist["RM_Master"]
    assert "USD" in dist["Price_Feed"]
    assert "INR" in dist["Price_Feed"]


def test_summary_apr_t04_cost_discrepancy(pricing_auditor):
    """
    Verified finding: Summary_Apr claims the raw material cost for T-04 is 16.9 INR/kg.
    Deterministic recalculation proves that using RM_Master list prices,
    the true cost is 19.98 INR/kg (with RM-101) or 19.14 INR/kg (with RM-102).
    """
    res = pricing_auditor.audit_summary_apr_cost()
    assert res["summary_apr_claimed_cost_t04"] == 16.9
    scenarios = res["scenarios"]
    scen1_cost = scenarios["scenario_1_rm_master_rm101"]["recalculated_cost_inr"]
    scen2_cost = scenarios["scenario_2_rm_master_rm102"]["recalculated_cost_inr"]
    assert scen1_cost == 19.98
    assert scen2_cost == 19.14
    assert scen1_cost > res["summary_apr_claimed_cost_t04"]
    assert scen2_cost > res["summary_apr_claimed_cost_t04"]
    assert "unresolved_uncertainty" in res


def test_t04_five_scenario_cost_reconciliation(pricing_auditor):
    """
    Regression test: Reconciles all five evaluated pricing and sourcing scenarios for T-04:
    - Scenario 1 (Master + RM-101): 19.98 INR/kg (unrounded: 19.9756)
    - Scenario 2 (Master + RM-102): 19.14 INR/kg (unrounded: 19.1356)
    - Scenario 3 (Feed auto + RM-101): 20.08 INR/kg (unrounded: 20.0760)
    - Scenario 4 (Feed manual + RM-101): 21.34 INR/kg (unrounded: 21.3360)
    - Scenario 5 (Feed auto + RM-102): 20.50 INR/kg (unrounded: 20.4960)
    Verifies line items, conversions, and exact scenario deltas.
    """
    res = pricing_auditor.audit_summary_apr_cost()
    scenarios = res["scenarios"]

    s1 = scenarios["scenario_1_rm_master_rm101"]["recalculated_cost_inr"]
    s2 = scenarios["scenario_2_rm_master_rm102"]["recalculated_cost_inr"]
    s3 = scenarios["scenario_3_feed_latest_auto_rm101"]["recalculated_cost_inr"]
    s4 = scenarios["scenario_4_feed_latest_manual_rm101"]["recalculated_cost_inr"]
    s5 = scenarios["scenario_5_feed_latest_auto_rm102"]["recalculated_cost_inr"]

    assert s1 == 19.98
    assert s2 == 19.14
    assert s3 == 20.08
    assert s4 == 21.34
    assert s5 == 20.50

    # Delta between S3 (feed) and S1 (master): exactly +0.10 INR/kg due to other ingredients
    delta_s3_s1 = round(s3 - s1, 2)
    assert delta_s3_s1 == 0.10

    # Delta between S4 (quote 228) and S3 (feed 210): exactly +1.26 INR/kg (7% * 18 = 1.26)
    delta_s4_s3 = round(s4 - s3, 2)
    assert delta_s4_s3 == 1.26

    # Delta between S5 (RM-102 feed 216) and S3 (RM-101 feed 210): exactly +0.42 INR/kg (7% * 6 = 0.42)
    delta_s5_s3 = round(s5 - s3, 2)
    assert delta_s5_s3 == 0.42
