"""
Automated Acceptance Tests for Kestrel R&D Formulation Assistant MVP.
Verifies deterministic validation, costing, unit normalization, evidence traceability,
and chemist approval gatekeeping.
"""

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import pytest

from kestrel_assistant.audit_log import AssistantAuditLogger
from kestrel_assistant.evidence_store import EvidenceStore
from kestrel_assistant.models import (
    CandidateFormulation,
    CheckStatus,
    FormulationRequest,
    FormulationStatus,
    IngredientLine,
    OverallValidationStatus,
)
from kestrel_assistant.recommender import FormulationRecommender
from kestrel_assistant.validator import DeterministicValidator

WORKBOOK_PATH = Path(__file__).resolve().parent.parent / "Kestrel_RnD_Export_2026-05.xlsx"
EXPECTED_WORKBOOK_HASH = "d64e01af845b13385076bb3cc6aa94485a9bc56159c990a238e64708bd5d2710"


@pytest.fixture(scope="module")
def assistant_components(tmp_path_factory):
    """Initializes shared assistant components against the read-only workbook with an isolated test audit log."""
    store = EvidenceStore(WORKBOOK_PATH)
    validator = DeterministicValidator()
    recommender = FormulationRecommender(store)
    log_dir = tmp_path_factory.mktemp("audit")
    logger = AssistantAuditLogger(log_dir / "assistant_audit_log.json")
    return store, validator, recommender, logger


# ============================================================================
# Criterion 1: Mass Balance Validation (Decimal Arithmetic)
# ============================================================================

def test_mass_balance_valid_passes(assistant_components):
    """Verifies that a formulation summing to exactly 100.0% passes mass balance validation."""
    _, validator, recommender, _ = assistant_components
    req = FormulationRequest()
    cand = recommender.generate_recommended_candidate(req)
    
    assert cand.total_percentage == Decimal("100.0")
    report = validator.validate(cand)
    mass_check = next(c for c in report.checks if c.check_id == "VAL-MASS-01")
    assert mass_check.status == CheckStatus.PASS


def test_mass_balance_invalid_fails(assistant_components):
    """
    Verifies that a formulation violating the 100.0% ± 0.05% tolerance
    (e.g., Trial T-09 summing to 103.0%) is rejected by the deterministic validator.
    """
    _, validator, recommender, _ = assistant_components
    cand_t09 = recommender.load_historical_trial_as_candidate("T-09")
    
    assert cand_t09.total_percentage == Decimal("103.0")
    report = validator.validate(cand_t09)
    assert report.can_approve is False
    mass_check = next(c for c in report.checks if c.check_id == "VAL-MASS-01")
    assert mass_check.status == CheckStatus.FAIL
    assert any("Mass balance violation" in err for err in report.rejection_reasons)


# ============================================================================
# Criterion 2: Physical Unit Normalization (Pa*s to cP)
# ============================================================================

def test_viscosity_unit_normalization_pas_to_cp(assistant_components):
    """
    Verifies that viscosity in Pa*s (Trial T-04: 0.45 Pa*s) is correctly normalized
    to 450.0 cP and flagged as exceeding the target range [50.0, 300.0] cP.
    """
    store, validator, recommender, _ = assistant_components
    t04_info = store.trials["T-04"]
    assert t04_info["viscosity_raw"] == "0.45 Pa·s"
    assert t04_info["viscosity_cp"] == 450.0

    cand_t04 = recommender.load_historical_trial_as_candidate("T-04")
    report = validator.validate(cand_t04)
    visc_check = next(c for c in report.checks if c.check_id == "VAL-PROP-VISC")
    assert visc_check.status == CheckStatus.FAIL
    assert "450.0 cP exceeds target interval" in visc_check.message


# ============================================================================
# Criterion 3: Packaging Unit Normalization (RM-170 Drum to kg)
# ============================================================================

def test_packaging_uom_normalization_drum_to_kg(assistant_components):
    """
    Verifies that RM-170 (priced at ₹32,800/drum of 200 kg in Price_Feed) is correctly
    normalized to ₹164.00/kg when the packaging basis is confirmed.
    """
    store, _, _, _ = assistant_components
    unit_price, basis, has_conflict, note = store.get_price_for_rm("RM-170", preferred_month="2026-05")
    
    assert unit_price == Decimal("164.0")
    assert "Normalized from" in basis or "200kg" in basis or "quote per kg" in basis


# ============================================================================
# Criterion 4: Conflicting Price Records Detection
# ============================================================================

def test_conflicting_price_records_detection(assistant_components):
    """
    Verifies that duplicate price records for the same RM in the same month
    (e.g., RM-101 in 2026-05 with ₹210 auto vs ₹228 manual quote) are flagged as conflicting.
    """
    store, _, _, _ = assistant_components
    unit_price, basis, has_conflict, conflict_note = store.get_price_for_rm("RM-101", preferred_month="2026-05")
    
    assert has_conflict is True
    assert "210" in conflict_note
    assert "228" in conflict_note


# ============================================================================
# Criterion 5: Ambiguous Synonym Detection & No Silent Merging
# ============================================================================

def test_ambiguous_synonym_tea_esterquat_not_silently_merged(assistant_components):
    """
    Verifies that the unmapped synonym token 'TEA-esterquat' maps to both RM-101 and RM-102,
    and is flagged as ambiguous rather than silently merged.
    """
    store, _, _, _ = assistant_components
    code, is_ambiguous, candidates, note = store.resolve_ingredient_token("TEA-esterquat")
    
    assert is_ambiguous is True
    assert code is None
    assert "RM-101" in candidates
    assert "RM-102" in candidates
    assert "Explicit chemist selection required" in note


# ============================================================================
# Criterion 6: Prohibited Silicone Hard Block
# ============================================================================

def test_prohibited_silicone_hard_block_trial_t10(assistant_components):
    """
    Verifies that a formulation containing silicone (Trial T-10 with RM-140 amino silicone)
    is strictly blocked when a silicone-free request is specified.
    """
    _, validator, recommender, _ = assistant_components
    cand_t10 = recommender.load_historical_trial_as_candidate("T-10")
    
    report = validator.validate(cand_t10)
    assert report.can_approve is False
    silicone_check = next(c for c in report.checks if c.check_id == "VAL-SAFE-03")
    assert silicone_check.status == CheckStatus.FAIL
    assert any("prohibited chemical" in err.lower() for err in report.rejection_reasons)


# ============================================================================
# Criterion 7: Missing / Contradictory Stability Evidence
# ============================================================================

def test_stability_contradiction_trial_t05(assistant_components):
    """
    Verifies that Trial T-05 is rejected for stability failure because Stability_Log
    explicitly records phase separation at Week 3 (45°C), contradicting the summary sheet 'Pass'.
    """
    _, validator, recommender, _ = assistant_components
    cand_t05 = recommender.load_historical_trial_as_candidate("T-05")
    
    assert cand_t05.stability_45c_4w_status == "FAIL"
    report = validator.validate(cand_t05)
    assert report.can_approve is False
    stab_check = next(c for c in report.checks if c.check_id == "VAL-EMP-STAB")
    assert stab_check.status == CheckStatus.FAIL


def test_stability_missing_data_trial_t11(assistant_components):
    """
    Verifies that Trial T-11 (incomplete stability) has stability status NOT_VERIFIED,
    and is never assumed or claimed as PASS by software without 4-week logs.
    """
    _, validator, recommender, _ = assistant_components
    cand_t11 = recommender.load_historical_trial_as_candidate("T-11")
    
    assert cand_t11.stability_45c_4w_status == "NOT_VERIFIED"
    report = validator.validate(cand_t11)
    stab_check = next(c for c in report.checks if c.check_id == "VAL-EMP-STAB")
    assert stab_check.status == CheckStatus.NOT_VERIFIED


# ============================================================================
# Criterion 8: Missing / Low Softness Panel Score Handling
# ============================================================================

def test_softness_panel_score_handling(assistant_components):
    """
    Verifies that missing panel data remains UNKNOWN, scores >= 4.0 pass,
    and scores < 4.0 are rejected against customer threshold.
    """
    _, validator, recommender, _ = assistant_components
    req = FormulationRequest(min_softness_panel_score=Decimal("4.0"))
    cand = recommender.generate_recommended_candidate(req)

    # Case A: Missing score -> UNKNOWN
    cand.softness_panel_score = None
    rep_none = validator.validate(cand)
    chk_none = next(c for c in rep_none.checks if c.check_id == "VAL-EMP-SOFT")
    assert chk_none.status == CheckStatus.UNKNOWN

    # Case B: Low score (3.5 < 4.0) -> FAIL
    cand.softness_panel_score = Decimal("3.5")
    rep_low = validator.validate(cand)
    chk_low = next(c for c in rep_low.checks if c.check_id == "VAL-EMP-SOFT")
    assert chk_low.status == CheckStatus.FAIL
    assert any("Sensory performance failure" in err for err in rep_low.rejection_reasons)

    # Case C: High score (4.2 >= 4.0) -> PASS
    cand.softness_panel_score = Decimal("4.2")
    rep_high = validator.validate(cand)
    chk_high = next(c for c in rep_high.checks if c.check_id == "VAL-EMP-SOFT")
    assert chk_high.status == CheckStatus.PASS


# ============================================================================
# Criterion 9: Chemist Approval Gatekeeping & Signature Enforcement
# ============================================================================

def test_chemist_approval_gate_blocks_invalid_candidate(assistant_components):
    """
    Verifies that a candidate with active validation failures (e.g. Trial T-09)
    cannot be approved for bench trial release.
    """
    _, validator, recommender, logger = assistant_components
    cand_t09 = recommender.load_historical_trial_as_candidate("T-09")
    report = validator.validate(cand_t09)

    assert report.can_approve is False
    with pytest.raises(ValueError, match="Cannot record chemist approval"):
        logger.record_chemist_approval(
            candidate=cand_t09,
            report=report,
            chemist_id="CHM-01",
            chemist_name="Dr. Test",
            chemist_role="Senior Chemist",
            approval_notes="Attempted invalid release"
        )


def test_chemist_approval_gate_succeeds_on_valid_candidate(assistant_components):
    """
    Verifies that a valid candidate formulation can be successfully approved by an
    authenticated chemist, generating an immutable audit record and cryptographic token.
    """
    _, validator, recommender, logger = assistant_components
    req = FormulationRequest()
    cand = recommender.generate_recommended_candidate(req)
    report = validator.validate(cand)

    assert report.can_approve is True
    record = logger.record_chemist_approval(
        candidate=cand,
        report=report,
        chemist_id="CHM-882",
        chemist_name="Dr. Vikram Shah",
        chemist_role="Senior Formulation Chemist",
        approval_notes="Approved for Lab 2 bench mixer trial"
    )

    assert record.approval_token.startswith("SIG-")
    assert record.candidate_id == cand.candidate_id
    assert record.validation_status_at_approval == "PASSED"
    assert cand.status == FormulationStatus.APPROVED_FOR_BENCH


# ============================================================================
# Criterion 10: Source Workbook Hash Invariance
# ============================================================================

def test_source_workbook_remains_unmodified_during_audit():
    """
    Verifies that the original Excel workbook SHA-256 hash remains strictly unchanged
    and that all operations were performed in read-only mode.
    """
    assert WORKBOOK_PATH.exists()
    sha256_hash = hashlib.sha256()
    with open(WORKBOOK_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256_hash.update(chunk)
    
    current_hash = sha256_hash.hexdigest()
    assert current_hash == EXPECTED_WORKBOOK_HASH


# ============================================================================
# Priority 4 Regression Tests: Approval Semantics, Provenance & Tamper Evidence
# ============================================================================

def test_unknown_mandatory_evidence_never_appears_as_verified_pass(assistant_components):
    """
    Regression Test 1:
    Verifies that when mandatory stability or softness evidence is unverified or unknown,
    the validator never issues a verified PASS for performance certification, and never
    claims 'All validation checks passed'.
    """
    _, validator, recommender, _ = assistant_components
    req = FormulationRequest()
    cand = recommender.generate_recommended_candidate(req)

    # Candidate has unverified stability and unmeasured softness
    assert cand.stability_45c_4w_status == "NOT_VERIFIED"
    assert cand.softness_panel_score is None

    report = validator.validate(cand)

    # Can approve for bench trial release only, NOT for product performance certification
    assert report.can_approve is True
    assert report.can_certify_performance is False
    assert report.requires_experimental_acknowledgement is True
    assert report.overall_status == OverallValidationStatus.SPEC_PASSED_PENDING_EXPERIMENTAL
    
    # Textual claims must not claim all checks passed
    assert "All validation checks passed" not in report.summary_message
    assert "pending experimental laboratory verification" in report.summary_message.lower()


def test_candidate_with_explicit_prohibited_ingredient_cannot_be_approved(assistant_components):
    """
    Regression Test 2:
    Verifies that a candidate with an explicit prohibited ingredient (e.g. silicone RM-140)
    is strictly rejected and cannot be approved by a chemist.
    """
    _, validator, recommender, logger = assistant_components
    cand_t10 = recommender.load_historical_trial_as_candidate("T-10")
    report = validator.validate(cand_t10)

    assert report.can_approve is False
    assert report.overall_status == OverallValidationStatus.REJECTED_WITH_FAILURES

    with pytest.raises(ValueError, match="Cannot record chemist approval"):
        logger.record_chemist_approval(
            candidate=cand_t10,
            report=report,
            chemist_id="CHM-01",
            chemist_name="Dr. Safety",
            chemist_role="Senior Chemist",
            approval_notes="Attempted prohibited release",
        )


def test_recipe_change_after_validation_invalidates_previous_approval(assistant_components):
    """
    Regression Test 3:
    Verifies that modifying a candidate recipe after validation invalidates the previous
    validation report and causes backend approval to reject the stale submission.
    """
    _, validator, recommender, logger = assistant_components
    req = FormulationRequest()
    cand = recommender.generate_recommended_candidate(req)
    initial_report = validator.validate(cand)

    initial_hash = cand.compute_recipe_hash()
    assert initial_report.candidate_hash == initial_hash

    # Modify recipe composition after validation
    cand.ingredients[0].percentage += Decimal("0.50")
    cand.total_percentage += Decimal("0.50")
    modified_hash = cand.compute_recipe_hash()
    assert modified_hash != initial_hash

    # Submitting candidate with initial (stale) report must be rejected
    with pytest.raises(ValueError, match="candidate recipe has changed since validation was performed"):
        logger.record_chemist_approval(
            candidate=cand,
            report=initial_report,
            chemist_id="CHM-882",
            chemist_name="Dr. Vikram Shah",
            chemist_role="Senior Formulation Chemist",
            approval_notes="Attempted stale approval",
        )


def test_duplicate_approval_attempts_handled_deterministically(assistant_components):
    """
    Regression Test 4:
    Verifies that duplicate approval attempts for the exact same recipe version and chemist
    are detected and blocked to prevent accidental duplicate release events.
    """
    _, validator, recommender, logger = assistant_components
    req = FormulationRequest()
    cand = recommender.generate_recommended_candidate(req)
    cand.candidate_id = "CAND-IDEMPOTENT-01"
    report = validator.validate(cand)

    # First approval succeeds
    record1 = logger.record_chemist_approval(
        candidate=cand,
        report=report,
        chemist_id="CHM-901",
        chemist_name="Dr. Maya Patel",
        chemist_role="Senior Chemist",
        approval_notes="First release submission",
    )
    assert record1.approval_token.startswith("SIG-")

    # Second identical approval without changes is blocked
    with pytest.raises(ValueError, match="Duplicate approval prevented"):
        logger.record_chemist_approval(
            candidate=cand,
            report=report,
            chemist_id="CHM-901",
            chemist_name="Dr. Maya Patel",
            chemist_role="Senior Chemist",
            approval_notes="Accidental second click",
        )

    # Forcing duplicate explicitly is permitted if justified
    record2 = logger.record_chemist_approval(
        candidate=cand,
        report=report,
        chemist_id="CHM-901",
        chemist_name="Dr. Maya Patel",
        chemist_role="Senior Chemist",
        approval_notes="Intentional duplicate override",
        force_duplicate=True,
    )
    assert record2.approval_token != record1.approval_token


def test_historical_evidence_cannot_be_attributed_to_unrelated_candidate(assistant_components):
    """
    Regression Test 5:
    Verifies that historical test evidence from previous trials (such as T-06 softness score 4.5)
    is never automatically or silently attributed to a new, synthesized formulation candidate.
    """
    store, validator, recommender, _ = assistant_components
    req = FormulationRequest()
    cand = recommender.generate_recommended_candidate(req)

    # Candidate must not have historical softness or stability assumed
    assert cand.softness_panel_score is None
    assert cand.softness_provenance is None
    assert cand.stability_45c_4w_status == "NOT_VERIFIED"
    assert cand.stability_provenance is None

    # Load trial T-06 and verify its empirical score remains strictly bound to T-06
    cand_t06 = recommender.load_historical_trial_as_candidate("T-06")
    assert cand_t06.softness_panel_score is not None
    assert cand_t06.softness_provenance is not None
    assert cand_t06.softness_provenance.sheet_name == "Panel_Scores"
    assert cand_t06.source_trial_id == "T-06"


def test_conflicting_prices_remain_visible_and_not_silently_resolved(assistant_components):
    """
    Regression Test 6:
    Verifies that conflicting raw material prices (such as RM-101 in 2026-05) remain
    flagged and visible in validation warnings rather than being silently merged or averaged.
    """
    store, validator, recommender, _ = assistant_components
    cand = recommender.generate_recommended_candidate(FormulationRequest())
    
    # RM-101 line has conflicting prices flagged in notes
    rm101_line = next(l for l in cand.ingredients if l.resolved_rm_code == "RM-101")
    assert "conflict" in (rm101_line.notes or "").lower()

    report = validator.validate(cand)
    assert any("conflict" in warn.lower() and "RM-101" in warn for warn in report.advisory_warnings)


def test_historical_regression_trials_expected_outcomes(assistant_components):
    """
    Regression Test 7:
    Verifies that golden historical regression trials T-04, T-05, T-09, T-10, and T-11
    continue to produce the expected validation outcomes and failure classifications.
    """
    _, validator, recommender, _ = assistant_components

    # T-04: Viscosity failure (450 cP > 300 cP limit)
    t04 = recommender.load_historical_trial_as_candidate("T-04")
    rep_t04 = validator.validate(t04)
    assert rep_t04.can_approve is False
    assert any("Viscosity out of specification" in e for e in rep_t04.rejection_reasons)

    # T-05: Phase separation at 45°C Week 3
    t05 = recommender.load_historical_trial_as_candidate("T-05")
    rep_t05 = validator.validate(t05)
    assert rep_t05.can_approve is False
    assert any("Stability rejection" in e for e in rep_t05.rejection_reasons)

    # T-09: Stoichiometry sum violation (103.0%)
    t09 = recommender.load_historical_trial_as_candidate("T-09")
    rep_t09 = validator.validate(t09)
    assert rep_t09.can_approve is False
    assert any("Mass balance violation" in e for e in rep_t09.rejection_reasons)

    # T-10: Silicone contamination (RM-140)
    t10 = recommender.load_historical_trial_as_candidate("T-10")
    rep_t10 = validator.validate(t10)
    assert rep_t10.can_approve is False
    assert any("prohibited chemical" in e.lower() for e in rep_t10.rejection_reasons)

    # T-11: Incomplete stability testing (2 weeks only)
    t11 = recommender.load_historical_trial_as_candidate("T-11")
    rep_t11 = validator.validate(t11)
    assert rep_t11.can_certify_performance is False
    chk_stab = next(c for c in rep_t11.checks if c.check_id == "VAL-EMP-STAB")
    assert chk_stab.status == CheckStatus.NOT_VERIFIED


def test_audit_log_cryptographic_tamper_detection(tmp_path):
    """
    Regression Test 8:
    Verifies that cryptographic hash chaining in AssistantAuditLogger reliably detects
    any manual file editing, modified records, or severed hash chains.
    """
    test_log_file = tmp_path / "tamper_test_log.json"
    logger = AssistantAuditLogger(test_log_file)

    # Step 1: An empty or freshly initialized log passes
    is_valid, msg, records = logger.verify_log_tampering()
    assert is_valid is True

    # Step 2: Append 3 valid records
    validator = DeterministicValidator()
    req = FormulationRequest()
    store = EvidenceStore(WORKBOOK_PATH)
    recommender = FormulationRecommender(store)
    cand = recommender.generate_recommended_candidate(req)
    rep = validator.validate(cand)

    logger.log_validation_event(cand, rep, action="TEST_EVENT_1")
    logger.log_validation_event(cand, rep, action="TEST_EVENT_2")
    logger.record_chemist_approval(
        candidate=cand,
        report=rep,
        chemist_id="CHM-TEST",
        chemist_name="Dr. Integrity",
        chemist_role="Audit Auditor",
        approval_notes="Integrity test approval",
    )

    is_valid, msg, records = logger.verify_log_tampering()
    assert is_valid is True
    assert len(records) == 3

    # Step 3: Tamper with record 1 payload (e.g., change action or candidate_id)
    with open(test_log_file, "r", encoding="utf-8") as f:
        tampered_data = json.load(f)
    tampered_data[1]["action"] = "UNAUTHORIZED_MODIFIED_ACTION"
    with open(test_log_file, "w", encoding="utf-8") as f:
        json.dump(tampered_data, f, indent=2)

    # Step 4: Verify tampering is detected
    is_valid, msg, records = logger.verify_log_tampering()
    assert is_valid is False
    assert "Tamper detected" in msg
    assert "payload has been modified" in msg


def test_ph_interval_check_behavior(assistant_components):
    """
    Regression Test 9:
    Verifies that finished product pH within [3.5, 4.5] passes VAL-PROP-PH,
    and out-of-interval values produce advisory WARNING with clear bounds.
    """
    _, validator, recommender, _ = assistant_components
    req = FormulationRequest(ph_range=(Decimal("3.5"), Decimal("4.5")))
    cand = recommender.generate_recommended_candidate(req)

    # In range (4.0) -> PASS
    cand.estimated_ph = 4.0
    rep_ok = validator.validate(cand)
    ph_chk_ok = next(c for c in rep_ok.checks if c.check_id == "VAL-PROP-PH")
    assert ph_chk_ok.status == CheckStatus.PASS

    # Out of range (5.5 > 4.5) -> WARNING
    cand.estimated_ph = 5.5
    rep_warn = validator.validate(cand)
    ph_chk_warn = next(c for c in rep_warn.checks if c.check_id == "VAL-PROP-PH")
    assert ph_chk_warn.status == CheckStatus.WARNING
    assert "5.50" in ph_chk_warn.message


def test_viscosity_450cp_is_mandatory_hard_failure(assistant_components):
    """
    Regression Test 10:
    Verifies that a viscosity of 450.0 cP against a maximum of 300.0 cP
    is strictly a MANDATORY HARD FAILURE (blocking approval), not merely a warning.
    """
    _, validator, recommender, _ = assistant_components
    cand = recommender.generate_recommended_candidate(FormulationRequest())
    cand.estimated_viscosity_cp = 450.0

    report = validator.validate(cand)
    visc_chk = next(c for c in report.checks if c.check_id == "VAL-PROP-VISC")
    
    assert visc_chk.status == CheckStatus.FAIL
    assert visc_chk.is_blocking is True
    assert report.can_approve is False
    assert report.overall_status == OverallValidationStatus.REJECTED_WITH_FAILURES
    assert any("450.0 cP exceeds target interval" in err for err in report.rejection_reasons)


def test_recipe_optimization_water_rebalance(assistant_components):
    """
    Regression Test 11:
    Verifies that stoichiometrically rebalancing demineralized water (RM-180)
    restores total formulation mass to exactly 100.00% and resolves mass balance violations.
    """
    store, validator, recommender, _ = assistant_components
    cand = recommender.load_historical_trial_as_candidate("T-09")
    assert cand.total_percentage == Decimal("103.0")

    # Rebalance water (RM-180) to achieve 100.00%
    non_water = sum((l.percentage for l in cand.ingredients if l.resolved_rm_code != "RM-180"), Decimal("0.0"))
    water_needed = Decimal("100.00") - non_water

    updated = []
    for l in cand.ingredients:
        if l.resolved_rm_code == "RM-180":
            updated.append(IngredientLine(
                raw_token=l.raw_token,
                resolved_rm_code="RM-180",
                trade_name="Water (demineralised)",
                percentage=water_needed,
                unit_price_inr=Decimal("1.0"),
                cost_contribution_inr=(water_needed / Decimal("100.0")) * Decimal("1.0"),
            ))
        else:
            updated.append(l)

    cand.ingredients = updated
    cand.total_percentage = sum((l.percentage for l in updated), Decimal("0.0"))

    assert cand.total_percentage == Decimal("100.00")
    report = validator.validate(cand)
    mass_chk = next(c for c in report.checks if c.check_id == "VAL-MASS-01")
    assert mass_chk.status == CheckStatus.PASS

