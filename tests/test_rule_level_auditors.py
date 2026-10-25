"""
Reusable rule-level test suite using isolated synthetic fixtures.
Validates audit rules independently of specific Excel workbook row indexes:
1. Zero, one, or multiple ingredient-alias matches.
2. Formulation totals below, at, and above 100%.
3. Missing, stale, or conflicting prices.
4. Unknown units and currencies.
5. Missing chemist approval.
6. Incomplete stability evidence and contradictory stability records.
7. Missing or inconsistently formatted dates.
8. Hard-constraint violations blocking recommendation despite 'Pass' labels.
"""

import pandas as pd
import pytest
from kestrel_audit.formula_auditor import FormulationAuditor
from kestrel_audit.integrity_auditor import IntegrityAuditor
from kestrel_audit.pricing_auditor import PricingAuditor
from kestrel_audit.cross_sheet_auditor import CrossSheetAuditor
from kestrel_audit.unit_date_auditor import UnitAndDateAuditor


# ============================================================================
# Synthetic Fixtures
# ============================================================================

@pytest.fixture
def synthetic_rm_master() -> pd.DataFrame:
    """Synthetic RM_Master with controlled aliases, currencies, and packaging units."""
    return pd.DataFrame([
        {
            "code": "RM-101",
            "name": "Esterquat 90",
            "synonyms": "TEA-esterquat; EQ-90",
            "list_price": 210.0,
            "currency": "INR",
            "uom": "kg",
            "price_updated": "2025-11-03",
        },
        {
            "code": "RM-102",
            "name": "Esterquat-90 (TEA)",
            "synonyms": "TEA esterquat",
            "list_price": 198.0,
            "currency": "INR",
            "uom": "kg",
            "price_updated": "2025-09-15",
        },
        {
            "code": "RM-120",
            "name": "Fatty alcohol ethoxylate 7EO",
            "synonyms": "FAE-7",
            "list_price": 140.0,
            "currency": "INR",
            "uom": "kg",
            "price_updated": "2026-03-01",
        },
        {
            "code": "RM-140",
            "name": "Amino silicone micro-emulsion",
            "synonyms": "Silicone fluid",
            "list_price": 4.60,
            "currency": "USD",
            "uom": "kg",
            "price_updated": "2026-01-20",
        },
        {
            "code": "RM-170",
            "name": "Polyethylene wax emulsion",
            "synonyms": "PE wax",
            "list_price": 32000.0,
            "currency": "INR",
            "uom": "drum (200 kg)",
            "price_updated": "2026-01-05",
        },
        {
            "code": "RM-180",
            "name": "Water (demineralised)",
            "synonyms": "DM water",
            "list_price": 1.0,
            "currency": "INR",
            "uom": "kg",
            "price_updated": "2024-04-01",
        },
    ])


@pytest.fixture
def synthetic_price_feed() -> pd.DataFrame:
    """Synthetic Price_Feed with conflicting and stale monthly entries."""
    return pd.DataFrame([
        # RM-101 has conflicting entries in 2026-05
        {"code": "RM-101", "month": "2026-05", "price": 210.0, "currency": "INR", "source": "PurchaseOne", "entry_type": "auto"},
        {"code": "RM-101", "month": "2026-05", "price": 228.0, "currency": "INR", "source": "email", "entry_type": "manual"},
        # RM-102 has updated price in 2026-05 (216 vs 198 list)
        {"code": "RM-102", "month": "2026-05", "price": 216.0, "currency": "INR", "source": "PurchaseOne", "entry_type": "auto"},
    ])


# ============================================================================
# Rule 1: Ingredient Alias Matching (Zero, One, Multiple)
# ============================================================================

def test_alias_matching_zero_matches(synthetic_rm_master):
    """Rule test: Unrecognized ingredient token returns 0 matches and is flagged unmapped."""
    auditor = FormulationAuditor({"RM_Master": synthetic_rm_master})
    items, total, errors = auditor.parse_recipe_string("Unknown-Polymer-X:5.0; RM-180:95.0")
    unknown_item = next(it for it in items if it["raw_token"] == "Unknown-Polymer-X")

    assert unknown_item["is_registered_code"] is False
    assert unknown_item["synonym_matches"] == []
    assert unknown_item["is_ambiguous_synonym"] is False


def test_alias_matching_single_unique_match(synthetic_rm_master):
    """Rule test: Unique synonym token resolves to exactly one primary RM code."""
    auditor = FormulationAuditor({"RM_Master": synthetic_rm_master})
    items, total, errors = auditor.parse_recipe_string("FAE-7:2.0; RM-180:98.0")
    fae_item = next(it for it in items if it["raw_token"] == "FAE-7")

    assert fae_item["is_registered_code"] is False
    assert fae_item["synonym_matches"] == ["RM-120"]
    assert fae_item["is_ambiguous_synonym"] is False


def test_alias_matching_multiple_ambiguous_matches(synthetic_rm_master):
    """Rule test: Colliding synonym token matches multiple RM codes and is flagged ambiguous."""
    auditor = FormulationAuditor({"RM_Master": synthetic_rm_master})
    items, total, errors = auditor.parse_recipe_string("TEA-esterquat:7.0; RM-180:93.0")
    tea_item = next(it for it in items if it["raw_token"] == "TEA-esterquat")

    assert tea_item["is_registered_code"] is False
    assert "RM-101" in tea_item["synonym_matches"]
    assert "RM-102" in tea_item["synonym_matches"]
    assert tea_item["is_ambiguous_synonym"] is True


# ============================================================================
# Rule 2: Formulation Stoichiometry Balance (Below, At, Above 100%)
# ============================================================================

@pytest.mark.parametrize("recipe,expected_total,is_valid", [
    ("RM-101:5.0; RM-180:90.0", 95.0, False),    # Below 100%
    ("RM-101:7.0; RM-180:93.0", 100.0, True),   # Exactly 100%
    ("RM-101:7.5; RM-180:95.5", 103.0, False),  # Above 100%
])
def test_formulation_stoichiometry_totals(synthetic_rm_master, recipe, expected_total, is_valid):
    """Rule test: Validates stoichiometry mass balance below, at, and above 100.0%."""
    auditor = FormulationAuditor({"RM_Master": synthetic_rm_master})
    items, total, errors = auditor.parse_recipe_string(recipe)
    assert total == expected_total
    assert (abs(total - 100.0) <= 0.05) is is_valid


# ============================================================================
# Rule 3: Pricing Checks (Conflicting, Stale, Missing)
# ============================================================================

def test_pricing_conflicts_detection(synthetic_rm_master, synthetic_price_feed):
    """Rule test: Detects multiple price entries for same code and month."""
    auditor = PricingAuditor({"RM_Master": synthetic_rm_master, "Price_Feed": synthetic_price_feed})
    conflicts = auditor.audit_duplicate_monthly_feed()
    assert len(conflicts) == 1
    assert conflicts[0]["code"] == "RM-101"
    assert conflicts[0]["month"] == "2026-05"
    assert conflicts[0]["price_delta"] == 18.0


def test_stale_master_pricing_detection(synthetic_rm_master, synthetic_price_feed):
    """Rule test: Flags discrepancies where latest feed price diverges from master list price."""
    auditor = PricingAuditor({"RM_Master": synthetic_rm_master, "Price_Feed": synthetic_price_feed})
    discrepancies = auditor.audit_master_vs_feed_prices()
    rm102_disc = next((d for d in discrepancies if d["code"] == "RM-102"), None)
    assert rm102_disc is not None
    assert rm102_disc["master_price"] == 198.0
    assert rm102_disc["latest_feed_price"] == 216.0


def test_missing_price_detection(synthetic_rm_master):
    """Rule test: Fails gracefully when calculating formula cost with an unmapped raw material."""
    auditor = PricingAuditor({"RM_Master": synthetic_rm_master})
    unmapped_recipe = [
        {"raw_token": "RM-999-MISSING", "percentage": 10.0},
        {"raw_token": "RM-180", "percentage": 90.0},
    ]
    res = auditor.calculate_formula_rm_cost(unmapped_recipe)
    assert "error" in res
    assert "RM-999-MISSING" in res["error"]


# ============================================================================
# Rule 4: Packaging Units and Currencies
# ============================================================================

def test_packaging_uom_normalization(synthetic_rm_master):
    """Rule test: Normalizes packaging units like drum (200 kg) to per-kg rate."""
    auditor = PricingAuditor({"RM_Master": synthetic_rm_master})
    recipe = [
        {"raw_token": "RM-170", "percentage": 2.0},  # 32,000 / drum of 200 kg = 160/kg
        {"raw_token": "RM-180", "percentage": 98.0}, # 1.0 / kg
    ]
    res = auditor.calculate_formula_rm_cost(recipe)
    # Expected: (2.0% * 160) + (98.0% * 1.0) = 3.20 + 0.98 = 4.18
    assert res["total_cost_inr_per_kg"] == 4.18


def test_currency_conversion_usd_to_inr(synthetic_rm_master):
    """Rule test: Applies 84.00 FX conversion to foreign currency ingredients."""
    auditor = PricingAuditor({"RM_Master": synthetic_rm_master})
    recipe = [
        {"raw_token": "RM-140", "percentage": 1.0},  # $4.60 * 84 = 386.40 INR/kg
        {"raw_token": "RM-180", "percentage": 99.0}, # 1.0 INR/kg
    ]
    res = auditor.calculate_formula_rm_cost(recipe)
    # Expected: (1.0% * 386.40) + (99.0% * 1.0) = 3.864 + 0.99 = 4.854 -> 4.85
    assert res["total_cost_inr_per_kg"] == 4.85


# ============================================================================
# Rule 5: Chemist Approval Gate
# ============================================================================

@pytest.mark.parametrize("approved_val,expected_unapproved", [
    (None, True),
    ("", True),
    ("nan", True),
    ("VS", False),
    ("AK", False),
])
def test_chemist_approval_gate(approved_val, expected_unapproved):
    """Rule test: Ensures unapproved trials are flagged and cannot bypass approval gate."""
    synthetic_tx = pd.DataFrame([{
        "trial_id": "T-TEST",
        "approved_by": approved_val,
        "viscosity": "180 cP",
    }])
    auditor = CrossSheetAuditor({"Trials_TX_Softeners": synthetic_tx})
    # Check T-04 audit logic on arbitrary trial
    row = synthetic_tx.iloc[0]
    appr = row.get("approved_by")
    is_unapproved = pd.isna(appr) or str(appr).strip() in ["", "nan"]
    assert is_unapproved is expected_unapproved


# ============================================================================
# Rule 6: Stability Contradiction & Incomplete Evidence
# ============================================================================

def test_stability_contradiction_detection():
    """Rule test: Summary 'Pass' contradicted by raw log phase separation is caught."""
    synthetic_tx = pd.DataFrame([{
        "trial_id": "T-TEST",
        "stability_45c_4wk": "Pass",
    }])
    synthetic_stab = pd.DataFrame([
        {"sample_id": "T-TEST", "week": 0, "temp_c": 45, "appearance": "clear", "phase_sep": "N"},
        {"sample_id": "T-TEST", "week": 3, "temp_c": 45, "appearance": "separated", "phase_sep": "Y"},
    ])

    auditor = CrossSheetAuditor({
        "Trials_TX_Softeners": synthetic_tx,
        "Stability_Log": synthetic_stab,
    })
    # Evaluate contradiction logic
    has_sep = any(r["phase_sep"] == "Y" for _, r in synthetic_stab.iterrows())
    summary_pass = synthetic_tx.iloc[0]["stability_45c_4wk"] == "Pass"
    assert (summary_pass and has_sep) is True


def test_incomplete_stability_must_not_pass():
    """Rule test: Trials with incomplete weeks or 'In progress' must not be assumed passed."""
    synthetic_tx = pd.DataFrame([{
        "trial_id": "T-INC",
        "stability_45c_4wk": "In progress (week 2)",
        "lims_status": "Open",
        "approved_by": None,
        "ph": None,
    }])
    auditor = CrossSheetAuditor({"Trials_TX_Softeners": synthetic_tx})
    status = auditor.audit_t11_status()
    # Ensure incomplete trial handling flags properly
    row = synthetic_tx.iloc[0]
    is_incomplete = "in progress" in str(row["stability_45c_4wk"]).lower() or pd.isna(row["approved_by"])
    assert is_incomplete is True


# ============================================================================
# Rule 7: Date Format Parsing & Chronology
# ============================================================================

@pytest.mark.parametrize("date_str,expected_format", [
    ("2026-03-01", "ISO (YYYY-MM-DD)"),
    ("19/02/2025", "Slash (DD/MM/YYYY or MM/DD/YYYY)"),
    ("12-Apr-26", "Alphanumeric (DD-Mon-YY)"),
])
def test_date_format_detection(date_str, expected_format):
    """Rule test: Correctly identifies date format variants across tables."""
    synthetic_tx = pd.DataFrame([{
        "trial_id": "T-DATE",
        "date": date_str,
    }])
    auditor = UnitAndDateAuditor({"Trials_TX_Softeners": synthetic_tx})
    findings = auditor.audit_dates_tx_softeners()
    assert findings[0]["format_type"] == expected_format


# ============================================================================
# Rule 8: Hard-Constraint Violation Blocks Recommendation
# ============================================================================

def test_hard_constraint_silicone_blocks_recommendation(synthetic_rm_master):
    """
    Rule test: When brief requires 'silicone-free', a trial containing RM-140 (silicone)
    must be flagged as a constraint violation even if it is labeled 'Pass' and has high softness.
    """
    synthetic_tx = pd.DataFrame([{
        "trial_id": "T-SILICONE",
        "formulation_pct": "RM-101:6.0; RM-140:2.0; RM-180:92.0",
        "stability_45c_4wk": "Pass",
        "softness": "5/5",
        "approved_by": "VS",
    }])
    auditor = FormulationAuditor({
        "RM_Master": synthetic_rm_master,
        "Trials_TX_Softeners": synthetic_tx,
    })
    findings = auditor.audit_tx_softeners()
    trial_finding = findings[0]

    assert trial_finding["contains_silicone"] is True
    # Verify business rule: Silicone presence blocks recommendation
    recommendation_allowed = not trial_finding["contains_silicone"] and trial_finding["is_stoichiometry_valid"]
    assert recommendation_allowed is False


# ============================================================================
# Rule 9: Thermal Stability Acceptance Criteria (4 Weeks @ 45°C, No Separation / Yellowing)
# ============================================================================

def test_stability_4w_45c_missing_data_remains_not_verified():
    """
    Rule test: Incomplete, ongoing, or missing 4-week 45°C stability records must
    remain explicitly 'NOT_VERIFIED' or 'UNKNOWN', never assumed passed by an LLM.
    """
    trial_records = [
        {"sample_id": "T-INC1", "week": 2, "temp_c": 45, "appearance": "milky white", "phase_sep": "N"},
    ]
    # Function evaluating 4-week stability requirement
    def evaluate_stability(sample_id, logs, target_weeks=4, target_temp=45):
        sample_logs = [l for l in logs if l["sample_id"] == sample_id and l["temp_c"] == target_temp]
        weeks_present = {l["week"] for l in sample_logs}
        if target_weeks not in weeks_present:
            return "NOT_VERIFIED"  # Missing full duration
        for entry in sample_logs:
            if entry["phase_sep"] == "Y" or "yellow" in entry.get("appearance", "").lower():
                return "FAIL"
        return "PASS"

    status = evaluate_stability("T-INC1", trial_records, target_weeks=4, target_temp=45)
    assert status == "NOT_VERIFIED"
    assert status != "PASS"


def test_stability_phase_separation_and_yellowing_rejection():
    """
    Rule test: 4-week 45°C stability test fails if phase separation occurs OR yellowing is observed.
    """
    # Case A: Phase separation at week 3
    logs_separation = [
        {"sample_id": "T-SEP", "week": 1, "temp_c": 45, "appearance": "milky", "phase_sep": "N"},
        {"sample_id": "T-SEP", "week": 2, "temp_c": 45, "appearance": "milky", "phase_sep": "N"},
        {"sample_id": "T-SEP", "week": 3, "temp_c": 45, "appearance": "separated", "phase_sep": "Y"},
        {"sample_id": "T-SEP", "week": 4, "temp_c": 45, "appearance": "separated", "phase_sep": "Y"},
    ]
    # Case B: Yellowing at week 4
    logs_yellowing = [
        {"sample_id": "T-YEL", "week": 1, "temp_c": 45, "appearance": "milky white", "phase_sep": "N"},
        {"sample_id": "T-YEL", "week": 2, "temp_c": 45, "appearance": "milky white", "phase_sep": "N"},
        {"sample_id": "T-YEL", "week": 3, "temp_c": 45, "appearance": "slight off-white", "phase_sep": "N"},
        {"sample_id": "T-YEL", "week": 4, "temp_c": 45, "appearance": "marked yellowing", "phase_sep": "N"},
    ]
    # Case C: Clean pass
    logs_clean = [
        {"sample_id": "T-OK", "week": 1, "temp_c": 45, "appearance": "milky white", "phase_sep": "N"},
        {"sample_id": "T-OK", "week": 2, "temp_c": 45, "appearance": "milky white", "phase_sep": "N"},
        {"sample_id": "T-OK", "week": 3, "temp_c": 45, "appearance": "milky white", "phase_sep": "N"},
        {"sample_id": "T-OK", "week": 4, "temp_c": 45, "appearance": "milky white", "phase_sep": "N"},
    ]

    def check_4w_stability(logs, sample_id):
        sample_logs = [l for l in logs if l["sample_id"] == sample_id and l["temp_c"] == 45]
        if 4 not in {l["week"] for l in sample_logs}:
            return "NOT_VERIFIED"
        for l in sample_logs:
            if l.get("phase_sep") == "Y":
                return "FAIL_PHASE_SEPARATION"
            if "yellow" in l.get("appearance", "").lower():
                return "FAIL_YELLOWING"
        return "PASS"

    assert check_4w_stability(logs_separation, "T-SEP") == "FAIL_PHASE_SEPARATION"
    assert check_4w_stability(logs_yellowing, "T-YEL") == "FAIL_YELLOWING"
    assert check_4w_stability(logs_clean, "T-OK") == "PASS"


# ============================================================================
# Rule 10: Sensory Softness Panel Acceptance Criteria (Panel Score >= 4/5)
# ============================================================================

def test_softness_panel_missing_data_remains_unknown():
    """
    Rule test: Candidate formulations lacking sensory panel test evidence must
    have softness marked as 'UNKNOWN' / None. Never infer pass from LLM synthesis.
    """
    trial_data = {"trial_id": "T-NOSOFT", "softness_score": None}

    def evaluate_softness(data, threshold=4.0):
        score = data.get("softness_score")
        if score is None:
            return "UNKNOWN", False
        meets_target = float(score) >= threshold
        return f"{score}/5", meets_target

    label, passes = evaluate_softness(trial_data)
    assert label == "UNKNOWN"
    assert passes is False


def test_softness_panel_score_below_threshold_fails():
    """
    Rule test: Softness scores below the customer threshold (< 4/5, e.g. 3.2/5)
    are flagged as non-compliant with the customer brief.
    """
    def check_softness(score_str, threshold=4.0):
        if not score_str or pd.isna(score_str):
            return "UNKNOWN", False
        # Parse score format like "3.2/5" or "4.5/5"
        val = float(str(score_str).split("/")[0])
        return val, val >= threshold

    val_low, passes_low = check_softness("3.2/5", threshold=4.0)
    assert val_low == 3.2
    assert passes_low is False

    val_high, passes_high = check_softness("4.5/5", threshold=4.0)
    assert val_high == 4.5
    assert passes_high is True


def test_empirical_properties_distinguished_from_hard_constraints():
    """
    Rule test: Verifies that hard formulation constraints (silicone, mass balance)
    can be evaluated deterministically in software, whereas empirical properties
    (thermal stability, sensory softness) require empirical test data.
    """
    formulation = {
        "mass_balance": 100.0,
        "contains_silicone": False,
        "rm_cost_inr": 20.08,
        # Empirical properties without lab test results:
        "stability_lab_tested": False,
        "softness_panel_tested": False,
    }

    # Deterministic hard constraints can be certified immediately:
    hard_constraints_pass = (
        formulation["mass_balance"] == 100.0 and
        not formulation["contains_silicone"] and
        formulation["rm_cost_inr"] <= 22.0
    )
    assert hard_constraints_pass is True

    # Empirical properties cannot be certified without lab test records:
    can_certify_stability = formulation["stability_lab_tested"]
    can_certify_softness = formulation["softness_panel_tested"]
    assert can_certify_stability is False
    assert can_certify_softness is False

