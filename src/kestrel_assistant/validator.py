"""
Deterministic Validation Engine for Kestrel R&D Formulation Assistant.
Enforces zero-tolerance mathematical, safety, and evidence constraints using Python Decimal arithmetic.
Probabilistic LLMs are strictly forbidden from overriding these deterministic checks.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    CandidateFormulation,
    CheckStatus,
    FormulationRequest,
    OverallValidationStatus,
    ValidationCheck,
    ValidationReport,
)


class DeterministicValidator:
    """Zero-tolerance deterministic safety and constraint validation engine."""

    TOLERANCE_MASS_BALANCE = Decimal("0.05")  # 100.0% ± 0.05%
    TARGET_TOTAL_MASS = Decimal("100.00")
    IPA_ADVISORY_THRESHOLD = Decimal("1.00")  # Internal guideline: RM-131 <= 1.0%

    def __init__(self, request: Optional[FormulationRequest] = None):
        self.request = request or FormulationRequest()

    def validate(
        self,
        candidate: CandidateFormulation,
        require_chemist_approval: bool = False,
        reviewer_name: Optional[str] = None,
        experimental_acknowledgement_given: bool = False,
    ) -> ValidationReport:
        """
        Executes complete suite of deterministic checks on a candidate formulation.
        Returns a structured ValidationReport.
        """
        checks: List[ValidationCheck] = []
        rejection_reasons: List[str] = []
        advisory_warnings: List[str] = []

        # 1. Mass Balance Precision Check (Decimal)
        mass_check, mass_err = self._check_mass_balance(candidate)
        checks.append(mass_check)
        if mass_check.status == CheckStatus.FAIL:
            rejection_reasons.append(mass_err)

        # 2. Ingredient Identity & Synonym Ambiguity Check
        id_check, id_errs = self._check_ingredient_identities(candidate)
        checks.append(id_check)
        if id_check.status == CheckStatus.FAIL:
            rejection_reasons.extend(id_errs)

        # 3. Prohibited Chemical Hard-Block Check (Silicone)
        silicone_check, silicone_err = self._check_prohibited_ingredients(candidate)
        checks.append(silicone_check)
        if silicone_check.status == CheckStatus.FAIL:
            rejection_reasons.append(silicone_err)

        # 4. Internal Flammability / VOC Advisory Guideline (Isopropanol)
        ipa_check, ipa_warn = self._check_ipa_advisory(candidate)
        checks.append(ipa_check)
        if ipa_check.status == CheckStatus.WARNING:
            advisory_warnings.append(ipa_warn)

        # 5. Pricing & Raw-Material Cost Ceiling Check (Decimal)
        cost_check, cost_err, cost_warns = self._check_costing(candidate)
        checks.append(cost_check)
        if cost_check.status == CheckStatus.FAIL:
            rejection_reasons.append(cost_err)
        if cost_warns:
            advisory_warnings.extend(cost_warns)

        # 6. Physical Property Heuristic Constraints (Solids, pH, Viscosity)
        prop_checks, prop_errs = self._check_physical_properties(candidate)
        checks.extend(prop_checks)
        rejection_reasons.extend(prop_errs)

        # 7. Empirical Stability Grounding Check (4w @ 45°C)
        stab_check, stab_err = self._check_empirical_stability(candidate)
        checks.append(stab_check)
        if stab_check.status == CheckStatus.FAIL:
            rejection_reasons.append(stab_err)
        elif stab_check.status in (CheckStatus.NOT_VERIFIED, CheckStatus.UNKNOWN):
            advisory_warnings.append(
                f"Thermal stability status is {stab_check.status.value}: physical incubator testing required prior to commercial release."
            )

        # 8. Empirical Softness Panel Grounding Check (Score >= 4/5)
        soft_check, soft_err = self._check_empirical_softness(candidate)
        checks.append(soft_check)
        if soft_check.status == CheckStatus.FAIL:
            rejection_reasons.append(soft_err)
        elif soft_check.status in (CheckStatus.NOT_VERIFIED, CheckStatus.UNKNOWN):
            advisory_warnings.append(
                f"Sensory softness status is {soft_check.status.value}: sensory panel evaluation required prior to commercial release."
            )

        # Empirical verification booleans
        stab_verified = (stab_check.status == CheckStatus.PASS)
        soft_verified = (soft_check.status == CheckStatus.PASS)
        empirical_all_verified = stab_verified and soft_verified
        requires_experimental_acknowledgement = not empirical_all_verified

        # 9. Chemist Approval Governance Gate
        approval_check, approval_err = self._check_approval_gate(
            candidate,
            rejection_reasons=rejection_reasons,
            require_chemist_approval=require_chemist_approval,
            reviewer_name=reviewer_name,
            experimental_acknowledgement_given=experimental_acknowledgement_given,
            requires_acknowledgement=requires_experimental_acknowledgement,
        )
        checks.append(approval_check)
        if approval_check.status == CheckStatus.FAIL:
            rejection_reasons.append(approval_err)

        # Determine overall status and permissions
        has_fatal_fails = any(c.status == CheckStatus.FAIL and c.is_blocking for c in checks)
        can_approve = not has_fatal_fails
        can_certify_performance = (not has_fatal_fails) and empirical_all_verified

        candidate_hash = candidate.compute_recipe_hash()

        if has_fatal_fails:
            overall_status = OverallValidationStatus.REJECTED_WITH_FAILURES
            summary = f"REJECTED: Formulation fails {len(rejection_reasons)} mandatory validation criteria."
        elif requires_experimental_acknowledgement:
            overall_status = OverallValidationStatus.SPEC_PASSED_PENDING_EXPERIMENTAL
            unverified = []
            if not stab_verified:
                unverified.append("Thermal stability (4w @ 45°C)")
            if not soft_verified:
                unverified.append("Sensory softness panel")
            summary = (
                f"SPECIFICATION VALIDATED FOR BENCH TRIAL: Specification checks passed; "
                f"pending experimental laboratory verification of {', '.join(unverified)}. "
                f"Physical testing required before commercial release."
            )
        else:
            overall_status = OverallValidationStatus.ALL_CRITERIA_VERIFIED_PASS
            if advisory_warnings:
                summary = f"ALL CRITERIA VERIFIED (WITH ADVISORIES): All specifications and empirical performance requirements verified; {len(advisory_warnings)} advisory items noted."
            else:
                summary = "ALL CRITERIA VERIFIED: All deterministic specifications and empirical performance requirements verified."

        return ValidationReport(
            candidate_id=candidate.candidate_id,
            candidate_hash=candidate_hash,
            overall_status=overall_status,
            can_approve=can_approve,
            can_certify_performance=can_certify_performance,
            requires_experimental_acknowledgement=requires_experimental_acknowledgement,
            summary_message=summary,
            checks=checks,
            rejection_reasons=rejection_reasons,
            advisory_warnings=advisory_warnings,
        )

    # ------------------------------------------------------------------------
    # Individual Rule Implementations
    # ------------------------------------------------------------------------

    def _check_mass_balance(self, candidate: CandidateFormulation) -> Tuple[ValidationCheck, str]:
        """Validates sum of ingredient percentages equals 100.0% ± 0.05% using Decimal arithmetic."""
        total = sum((line.percentage for line in candidate.ingredients), Decimal("0.0"))
        delta = abs(total - self.TARGET_TOTAL_MASS)
        is_pass = delta <= self.TOLERANCE_MASS_BALANCE

        status = CheckStatus.PASS if is_pass else CheckStatus.FAIL
        msg = f"Total formulation mass is {total}% (Delta: {delta}%, Target: 100.00% ± 0.05%)"
        err = f"Mass balance violation: total concentration sum is {total}%, exceeding ±0.05% tolerance." if not is_pass else ""

        return ValidationCheck(
            check_id="VAL-MASS-01",
            category="Stoichiometry",
            check_name="Mass Balance Precision",
            status=status,
            message=msg,
            details={"total_pct": float(total), "delta_pct": float(delta), "target": 100.0},
            is_blocking=True,
        ), err

    def _check_ingredient_identities(self, candidate: CandidateFormulation) -> Tuple[ValidationCheck, List[str]]:
        """Ensures every ingredient token maps unambiguously to an active RM code."""
        unresolved = []
        ambiguous = []

        for line in candidate.ingredients:
            if line.is_ambiguous:
                ambiguous.append(f"{line.raw_token} -> matches {line.ambiguity_candidates}")
            elif not line.resolved_rm_code:
                unresolved.append(line.raw_token)

        errs = []
        if unresolved:
            errs.append(f"Unmapped ingredient tokens: {', '.join(unresolved)}")
        if ambiguous:
            errs.append(f"Ambiguous ingredient synonyms without explicit chemist selection: {'; '.join(ambiguous)}")

        is_pass = len(errs) == 0
        status = CheckStatus.PASS if is_pass else CheckStatus.FAIL
        msg = "All ingredient tokens uniquely and unambiguously mapped." if is_pass else "; ".join(errs)

        return ValidationCheck(
            check_id="VAL-ID-02",
            category="Identity & Traceability",
            check_name="Ingredient Identity Unambiguity",
            status=status,
            message=msg,
            details={"unresolved": unresolved, "ambiguous": ambiguous},
            is_blocking=True,
        ), errs

    def _check_prohibited_ingredients(self, candidate: CandidateFormulation) -> Tuple[ValidationCheck, str]:
        """Hard-blocks prohibited chemical classes (e.g. silicone-free constraint)."""
        prohibited = [p.lower() for p in self.request.prohibited_ingredients]
        detected = []

        for line in candidate.ingredients:
            code = (line.resolved_rm_code or "").lower()
            name = (line.trade_name or "").lower()
            chem_class = (line.chemical_class or "").lower()
            token = (line.raw_token or "").lower()

            for p in prohibited:
                if (p in code or p in name or p in chem_class or p in token) and line.percentage > Decimal("0.0"):
                    detected.append(f"{line.resolved_rm_code or line.raw_token} ({line.trade_name or line.chemical_class}): {line.percentage}%")

        is_pass = len(detected) == 0
        status = CheckStatus.PASS if is_pass else CheckStatus.FAIL
        msg = "No prohibited ingredients detected in formulation." if is_pass else f"Prohibited ingredient detected: {'; '.join(detected)}"
        err = f"Hard safety constraint violated: recipe contains prohibited chemical ({'; '.join(detected)})." if not is_pass else ""

        return ValidationCheck(
            check_id="VAL-SAFE-03",
            category="Safety & Compliance",
            check_name="Prohibited Ingredient Exclusion (Silicone-Free)",
            status=status,
            message=msg,
            details={"prohibited_classes": prohibited, "detected": detected},
            is_blocking=True,
        ), err

    def _check_ipa_advisory(self, candidate: CandidateFormulation) -> Tuple[ValidationCheck, str]:
        """
        Advisory threshold check for RM-131 (Isopropanol).
        Framed strictly as an internal R&D safety guideline, NOT a definitive legal conclusion.
        """
        ipa_pct = Decimal("0.0")
        for line in candidate.ingredients:
            if line.resolved_rm_code == "RM-131" or "isopropanol" in (line.trade_name or "").lower():
                ipa_pct += line.percentage

        exceeds = ipa_pct > self.IPA_ADVISORY_THRESHOLD
        status = CheckStatus.WARNING if exceeds else CheckStatus.PASS
        msg = f"Isopropanol (RM-131) concentration is {ipa_pct}% (Internal guideline threshold: <= 1.0%)"
        warn = f"Internal guideline advisory: Isopropanol content ({ipa_pct}%) exceeds 1.0% advisory threshold. Review flashpoint and ventilation protocol." if exceeds else ""

        return ValidationCheck(
            check_id="VAL-ADV-04",
            category="Safety & Compliance",
            check_name="Isopropanol Flammability Internal Advisory",
            status=status,
            message=msg,
            details={"ipa_concentration_pct": float(ipa_pct), "threshold_pct": 1.0},
            is_blocking=False,  # Advisory only
        ), warn

    def _check_costing(self, candidate: CandidateFormulation) -> Tuple[ValidationCheck, str, List[str]]:
        """Validates pricing availability, currency/UOM consistency, and cost ceiling."""
        total_cost = Decimal("0.0000")
        missing_prices = []
        pricing_warnings = []

        for line in candidate.ingredients:
            if line.percentage > Decimal("0.0"):
                if line.unit_price_inr is None:
                    missing_prices.append(line.resolved_rm_code or line.raw_token)
                else:
                    total_cost += line.cost_contribution_inr
                    if "conflict" in (line.notes or "").lower():
                        pricing_warnings.append(f"{line.resolved_rm_code}: {line.notes}")

        exceeds_budget = total_cost > self.request.max_cost_inr_per_kg
        has_missing = len(missing_prices) > 0

        if has_missing:
            status = CheckStatus.FAIL
            err = f"Pricing incomplete: missing price records for {', '.join(missing_prices)}."
            msg = err
        elif exceeds_budget:
            status = CheckStatus.FAIL
            err = f"Cost ceiling exceeded: total raw material cost is ₹{total_cost:.2f}/kg, exceeding limit of ₹{self.request.max_cost_inr_per_kg:.2f}/kg."
            msg = err
        else:
            status = CheckStatus.PASS
            err = ""
            msg = f"Total raw material cost is ₹{total_cost:.2f}/kg (Budget ceiling: ₹{self.request.max_cost_inr_per_kg:.2f}/kg)."

        return ValidationCheck(
            check_id="VAL-COST-05",
            category="Commercial Costing",
            check_name="Raw Material Cost Ceiling",
            status=status,
            message=msg,
            details={"total_cost_inr": float(total_cost), "max_cost_inr": float(self.request.max_cost_inr_per_kg), "missing": missing_prices},
            is_blocking=True,
        ), err, pricing_warnings

    def _check_physical_properties(self, candidate: CandidateFormulation) -> Tuple[List[ValidationCheck], List[str]]:
        """Checks estimated solids, pH, and viscosity against target intervals."""
        checks = []
        errs = []

        # Solids %
        min_solids, max_solids = self.request.solids_pct_range
        solids = candidate.estimated_solids_pct
        solids_ok = (min_solids <= solids <= max_solids)
        checks.append(ValidationCheck(
            check_id="VAL-PROP-SOLIDS",
            category="Physical Specifications",
            check_name="Active Solids Concentration",
            status=CheckStatus.PASS if solids_ok else CheckStatus.WARNING,
            message=f"Estimated solids: {solids}% (Target range: {min_solids}%–{max_solids}%)",
            details={"estimated_solids": float(solids), "target_min": float(min_solids), "target_max": float(max_solids)},
            is_blocking=False,
        ))

        # Viscosity cP (handles Pa*s normalization e.g. 0.45 Pa*s = 450 cP)
        min_visc, max_visc = self.request.viscosity_cp_range
        visc = candidate.estimated_viscosity_cp
        visc_ok = (float(min_visc) <= visc <= float(max_visc))
        v_status = CheckStatus.PASS if visc_ok else CheckStatus.FAIL
        v_err = f"Viscosity out of specification: {visc:.1f} cP exceeds target interval [{min_visc}, {max_visc}] cP." if not visc_ok else ""
        v_msg = v_err if not visc_ok else f"Estimated/measured viscosity: {visc:.1f} cP (Target: {min_visc}–{max_visc} cP)"
        if not visc_ok:
            errs.append(v_err)

        checks.append(ValidationCheck(
            check_id="VAL-PROP-VISC",
            category="Physical Specifications",
            check_name="Viscosity Interval Enforcement",
            status=v_status,
            message=v_msg,
            details={"viscosity_cp": visc, "target_min_cp": float(min_visc), "target_max_cp": float(max_visc)},
            is_blocking=True,
        ))

        # pH Range
        min_ph, max_ph = self.request.ph_range
        ph = candidate.estimated_ph
        ph_ok = (float(min_ph) <= ph <= float(max_ph))
        checks.append(ValidationCheck(
            check_id="VAL-PROP-PH",
            category="Physical Specifications",
            check_name="Finished Product pH Interval",
            status=CheckStatus.PASS if ph_ok else CheckStatus.WARNING,
            message=f"Estimated/measured pH: {ph:.2f} (Target range: {min_ph}–{max_ph})",
            details={"estimated_ph": float(ph), "target_min": float(min_ph), "target_max": float(max_ph)},
            is_blocking=False,
        ))

        return checks, errs

    def _check_empirical_stability(self, candidate: CandidateFormulation) -> Tuple[ValidationCheck, str]:
        """
        Validates empirical stability against 4w @ 45°C requirement.
        Missing or incomplete data must remain UNKNOWN / NOT_VERIFIED, NEVER inferred passed.
        """
        status_val = candidate.stability_45c_4w_status.upper()
        summary = candidate.stability_evidence_summary

        if status_val == "PASS":
            status = CheckStatus.PASS
            msg = f"Verified 4w @ 45°C stability evidence linked: {summary}"
            err = ""
        elif status_val == "FAIL":
            status = CheckStatus.FAIL
            msg = f"Stability failure documented: {summary}"
            err = f"Stability rejection: candidate recipe has documented failure at 45°C ({summary})."
        else:
            status = CheckStatus.NOT_VERIFIED
            msg = f"Stability not verified: {summary}. Mandatory laboratory incubator test required."
            err = ""

        return ValidationCheck(
            check_id="VAL-EMP-STAB",
            category="Empirical Lab Evidence",
            check_name="Thermal Stability Grounding (4w @ 45°C)",
            status=status,
            message=msg,
            details={"empirical_status": status_val, "evidence_summary": summary},
            is_blocking=(status == CheckStatus.FAIL),
        ), err

    def _check_empirical_softness(self, candidate: CandidateFormulation) -> Tuple[ValidationCheck, str]:
        """
        Validates empirical sensory softness against target threshold (>= 4.0/5.0).
        Missing panel data must remain UNKNOWN, NEVER inferred passed.
        """
        score = candidate.softness_panel_score
        target = self.request.min_softness_panel_score

        if score is None:
            status = CheckStatus.UNKNOWN
            msg = "Softness panel score is UNKNOWN (No sensory panel records linked). Empirical bench panel testing required."
            err = ""
        elif score >= target:
            status = CheckStatus.PASS
            msg = f"Verified panel softness score is {score:.1f}/5.0 (Meets target >= {target:.1f}/5.0)."
            err = ""
        else:
            status = CheckStatus.FAIL
            msg = f"Softness score {score:.1f}/5.0 is below required target of {target:.1f}/5.0."
            err = f"Sensory performance failure: panel score {score:.1f}/5.0 fails customer softness threshold ({target:.1f}/5.0)."

        return ValidationCheck(
            check_id="VAL-EMP-SOFT",
            category="Empirical Lab Evidence",
            check_name="Sensory Softness Panel Grounding",
            status=status,
            message=msg,
            details={"panel_score": float(score) if score is not None else None, "target_score": float(target)},
            is_blocking=(status == CheckStatus.FAIL),
        ), err

    def _check_approval_gate(
        self,
        candidate: CandidateFormulation,
        rejection_reasons: List[str],
        require_chemist_approval: bool,
        reviewer_name: Optional[str],
        experimental_acknowledgement_given: bool = False,
        requires_acknowledgement: bool = False,
    ) -> Tuple[ValidationCheck, str]:
        """
        Governance gate: Zero automated physical lab booking.
        State transition to APPROVED_FOR_BENCH strictly requires:
        1. All mandatory deterministic checks to pass (no blockers).
        2. Authenticated chemist name/identity provided.
        3. If stability or softness are unverified, explicit chemist experimental risk acknowledgement.
        """
        if not require_chemist_approval:
            return ValidationCheck(
                check_id="VAL-GOV-GATE",
                category="Chemist Governance",
                check_name="Chemist Approval Gatekeeper",
                status=CheckStatus.PASS,
                message="Proposal currently in DRAFT / REVIEW state (No bench execution scheduled).",
                details={"current_status": candidate.status.value},
                is_blocking=False,
            ), ""

        # Transition to APPROVED_FOR_BENCH requested:
        has_blockers = len(rejection_reasons) > 0
        has_reviewer = reviewer_name is not None and reviewer_name.strip() != ""

        if has_blockers:
            status = CheckStatus.FAIL
            err = f"Approval blocked: cannot approve candidate with active validation failures ({len(rejection_reasons)} blockers)."
            msg = err
        elif not has_reviewer:
            status = CheckStatus.FAIL
            err = "Approval blocked: authenticated chemist reviewer signature identity is required."
            msg = err
        elif requires_acknowledgement and not experimental_acknowledgement_given:
            status = CheckStatus.FAIL
            err = (
                "Approval blocked: candidate has unverified empirical properties (stability and/or softness). "
                "Explicit chemist experimental risk acknowledgement is required for bench trial release."
            )
            msg = err
        else:
            status = CheckStatus.PASS
            err = ""
            msg = f"Approved for laboratory bench trial by authenticated chemist: {reviewer_name}."

        return ValidationCheck(
            check_id="VAL-GOV-GATE",
            category="Chemist Governance",
            check_name="Chemist Approval Gatekeeper",
            status=status,
            message=msg,
            details={
                "requested_status": "APPROVED_FOR_BENCH",
                "reviewer": reviewer_name,
                "blockers_count": len(rejection_reasons),
                "experimental_acknowledgement_given": experimental_acknowledgement_given,
            },
            is_blocking=True,
        ), err

