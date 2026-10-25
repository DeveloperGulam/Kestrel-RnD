"""
Tests for formulation stoichiometry, unmapped ingredient tokens,
and project brief constraints (silicone-free, alcohol flammability).
"""

import pytest


def test_trial_t09_stoichiometry_sum_failure(formula_auditor):
    """
    Verified finding: Trial T-09 formulation percentages total 103.00%,
    failing standard 100% stoichiometry balance.
    """
    findings = {f["trial_id"]: f for f in formula_auditor.audit_tx_softeners()}
    assert "T-09" in findings
    t09 = findings["T-09"]
    assert t09["is_stoichiometry_valid"] is False
    assert t09["total_percentage"] == 103.0


def test_distinguish_tea_esterquat_token_from_trial_t04(formula_auditor):
    """
    Verified requirement: Correctly distinguish the unmapped ingredient token
    'TEA-esterquat' from the trial ID 'T-04'.
    In Trial T-04, the recipe specifies 'TEA-esterquat:7.0' which is an unmapped synonym token,
    not a registered RM code.
    """
    findings = {f["trial_id"]: f for f in formula_auditor.audit_tx_softeners()}
    assert "T-04" in findings
    t04 = findings["T-04"]

    # Verify trial ID is T-04
    assert t04["trial_id"] == "T-04"

    # Verify 'TEA-esterquat' is detected as an unmapped token
    assert "TEA-esterquat" in t04["unmapped_tokens"]


def test_tea_esterquat_synonym_ambiguity(formula_auditor, sheets):
    """
    Verified finding: In RM_Master, the token 'TEA-esterquat' is an ambiguous synonym
    matching BOTH RM-101 (Supplier A, list_price 210 INR) and RM-102 (Supplier B, list_price 198 INR).
    It cannot be silently merged without distorting cost and material provenance.
    """
    df_rm = sheets["RM_Master"].set_index("code")
    rm101_syn = str(df_rm.loc["RM-101", "synonyms"]).lower()
    rm102_syn = str(df_rm.loc["RM-102", "synonyms"]).lower()

    assert "tea-esterquat" in rm101_syn
    assert "tea esterquat" in rm102_syn

    # Check formula auditor ambiguity detection
    findings = {f["trial_id"]: f for f in formula_auditor.audit_tx_softeners()}
    t04 = findings["T-04"]
    ambiguous_tokens = t04["ambiguous_tokens"]
    assert len(ambiguous_tokens) >= 1
    amb = next(a for a in ambiguous_tokens if a["token"] == "TEA-esterquat")
    assert "RM-101" in amb["candidate_codes"]
    assert "RM-102" in amb["candidate_codes"]


def test_trial_t10_contains_silicone(formula_auditor):
    """
    Verified finding: Trial T-10 uses RM-140 (Amino silicone micro-emulsion),
    violating the customer brief's core constraint: 'silicone-free cationic softener'.
    """
    findings = {f["trial_id"]: f for f in formula_auditor.audit_tx_softeners()}
    assert "T-10" in findings
    assert findings["T-10"]["contains_silicone"] is True


def test_trial_t06_flammable_alcohol_excess(formula_auditor):
    """
    Verified finding: Trial T-06 uses RM-131 (Isopropanol) at 2.0%,
    which exceeds the 1.0% flammability threshold noted in Regulatory_Notes.
    """
    findings = {f["trial_id"]: f for f in formula_auditor.audit_tx_softeners()}
    assert "T-06" in findings
    assert findings["T-06"]["flammable_alcohol_excess"] is True
