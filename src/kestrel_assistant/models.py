"""
Pydantic data contracts for the Kestrel R&D Formulation Assistant.
Enforces strict typing, Decimal arithmetic, and explicit evidence provenance.
"""

from decimal import Decimal
from enum import Enum
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class FormulationStatus(str, Enum):
    DRAFT = "DRAFT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED_FOR_BENCH = "APPROVED_FOR_BENCH"
    REJECTED = "REJECTED"


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"
    NOT_VERIFIED = "NOT_VERIFIED"


class OverallValidationStatus(str, Enum):
    ALL_CRITERIA_VERIFIED_PASS = "ALL_CRITERIA_VERIFIED_PASS"
    SPEC_PASSED_PENDING_EXPERIMENTAL = "SPEC_PASSED_PENDING_EXPERIMENTAL"
    REJECTED_WITH_FAILURES = "REJECTED_WITH_FAILURES"


class ValueProvenanceType(str, Enum):
    CALCULATED = "CALCULATED"
    ESTIMATED_HEURISTIC = "ESTIMATED_HEURISTIC"
    EXPERIMENTALLY_MEASURED = "EXPERIMENTALLY_MEASURED"
    UNVERIFIED_PENDING_LAB = "UNVERIFIED_PENDING_LAB"


class EvidenceProvenance(BaseModel):
    """Explicit record-level audit trail for empirical test evidence."""
    sheet_name: str = Field(description="Workbook source sheet, e.g. Stability_Log, Panel_Scores")
    record_id: str = Field(description="Sample / row / trial identifier")
    test_conditions: str = Field(description="Environmental conditions, e.g. 45°C, 4 weeks, incubator STAB-CH1")
    test_date: str = Field(description="Date recorded in laboratory logs")
    observer: str = Field(description="Chemist or panel technician initials")
    raw_measurements: Dict[str, Any] = Field(default_factory=dict, description="Raw logged values")
    provenance_type: ValueProvenanceType = Field(default=ValueProvenanceType.EXPERIMENTALLY_MEASURED)
    linkage_rationale: str = Field(default="Direct historical test record for this formulation sample ID")


class FormulationRequest(BaseModel):
    """Structured intake for customer formulation requirements."""
    request_id: str = Field(default="REQ-2026-001", description="Identifier for customer request")
    customer_name: str = Field(default="Sunvale Mills", description="Customer or brand entity")
    target_substrate: str = Field(default="100% Cotton Knits / Terry Towels", description="Application textile substrate")
    solids_pct_range: Tuple[Decimal, Decimal] = Field(
        default=(Decimal("6.0"), Decimal("8.0")),
        description="Target active solids percentage [min, max]"
    )
    ph_range: Tuple[Decimal, Decimal] = Field(
        default=(Decimal("3.5"), Decimal("4.5")),
        description="Target finished product pH [min, max]"
    )
    viscosity_cp_range: Tuple[Decimal, Decimal] = Field(
        default=(Decimal("50.0"), Decimal("300.0")),
        description="Target Brookfield viscosity in cP at 25°C [min, max]"
    )
    max_cost_inr_per_kg: Decimal = Field(
        default=Decimal("22.00"),
        description="Maximum raw material cost ceiling in INR per kg"
    )
    prohibited_ingredients: List[str] = Field(
        default_factory=lambda: ["silicone", "RM-140"],
        description="List of restricted chemicals or classes (e.g. silicone-free)"
    )
    target_stability: str = Field(
        default="4 weeks at 45°C with no phase separation or yellowing",
        description="Thermal stability specification"
    )
    min_softness_panel_score: Decimal = Field(
        default=Decimal("4.0"),
        description="Minimum sensory softness panel score on 1-5 scale"
    )


class IngredientLine(BaseModel):
    """Single raw material ingredient line in a formulation."""
    raw_token: str = Field(description="Ingredient token from recipe string or input")
    resolved_rm_code: Optional[str] = Field(default=None, description="Master RM code (e.g. RM-101)")
    trade_name: str = Field(default="", description="Trade name from RM_Master")
    chemical_class: str = Field(default="", description="Chemical family/class")
    supplier: str = Field(default="", description="Approved primary supplier")
    percentage: Decimal = Field(description="Concentration in formulation percentage w/w")
    unit_price_inr: Optional[Decimal] = Field(default=None, description="Authoritative normalized price in INR/kg")
    price_basis: str = Field(default="Unknown", description="Source of price (e.g. Price_Feed, RM_Master list, drum normalized)")
    cost_contribution_inr: Decimal = Field(default=Decimal("0.0000"), description="Line cost contribution (percentage / 100 * price)")
    is_ambiguous: bool = Field(default=False, description="Whether ingredient token matches multiple RM codes")
    ambiguity_candidates: List[str] = Field(default_factory=list, description="Candidate RM codes if ambiguous")
    notes: Optional[str] = Field(default=None, description="Audit notes or pricing warnings")


class CandidateFormulation(BaseModel):
    """Candidate formulation recipe proposed for review and laboratory bench trial."""
    candidate_id: str = Field(default="CAND-TX-001", description="Unique candidate identifier")
    title: str = Field(default="Textile Softener Candidate", description="Descriptive title")
    substrate: str = Field(default="Cotton", description="Target substrate")
    ingredients: List[IngredientLine] = Field(default_factory=list, description="List of formulation ingredients")
    total_percentage: Decimal = Field(default=Decimal("0.0"), description="Sum of ingredient percentages [CALCULATED]")
    total_cost_inr_per_kg: Decimal = Field(default=Decimal("0.00"), description="Total formula raw-material cost in INR/kg [CALCULATED]")
    estimated_solids_pct: Decimal = Field(default=Decimal("0.0"), description="Calculated or estimated active solids % [ESTIMATED]")
    estimated_ph: float = Field(default=4.0, description="Heuristic estimated pH [ESTIMATED]")
    estimated_viscosity_cp: float = Field(default=150.0, description="Heuristic estimated viscosity in cP [ESTIMATED]")
    
    # Empirical properties (strictly require lab evidence; never LLM-hallucinated)
    stability_45c_4w_status: str = Field(default="NOT_VERIFIED", description="Empirical stability status: PASS, FAIL, NOT_VERIFIED")
    stability_evidence_summary: str = Field(default="No verified 4w @ 45°C incubator log linked", description="Evidence details")
    stability_provenance: Optional[EvidenceProvenance] = Field(default=None, description="Linked incubator log evidence")
    
    softness_panel_score: Optional[Decimal] = Field(default=None, description="Sensory panel score (e.g. 4.2), None if unmeasured")
    softness_evidence_summary: str = Field(default="No panel sensory test records linked", description="Evidence details")
    softness_provenance: Optional[EvidenceProvenance] = Field(default=None, description="Linked sensory panel evidence")
    
    source_trial_id: Optional[str] = Field(default=None, description="Parent historical trial reference if adapted")
    status: FormulationStatus = Field(default=FormulationStatus.DRAFT, description="Governance lifecycle status")
    validation_hash: Optional[str] = Field(default=None, description="Candidate recipe SHA-256 at last validation")

    def compute_recipe_hash(self) -> str:
        """Computes deterministic SHA-256 hash of formulation composition and concentrations."""
        repr_dict = {
            "candidate_id": self.candidate_id,
            "ingredients": [
                {
                    "raw_token": l.raw_token,
                    "resolved_rm": l.resolved_rm_code,
                    "percentage": str(l.percentage),
                    "price": str(l.unit_price_inr) if l.unit_price_inr is not None else None,
                }
                for l in self.ingredients
            ],
            "total_percentage": str(self.total_percentage),
            "total_cost": str(self.total_cost_inr_per_kg),
        }
        raw_bytes = json.dumps(repr_dict, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()


class ValidationCheck(BaseModel):
    """Individual deterministic check result."""
    check_id: str
    category: str  # e.g. "Stoichiometry", "Safety", "Costing", "Empirical Evidence", "Governance"
    check_name: str
    status: CheckStatus
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    is_blocking: bool = True  # If True, FAIL blocks bench trial release


class ValidationReport(BaseModel):
    """Comprehensive validation result across all deterministic and evidence checks."""
    candidate_id: str
    candidate_hash: str
    overall_status: OverallValidationStatus
    can_approve: bool  # Can proceed to bench trial (if experimental risks acknowledged)
    can_certify_performance: bool  # True ONLY if stability == PASS and softness == PASS
    requires_experimental_acknowledgement: bool  # True if stability or softness not verified
    summary_message: str
    checks: List[ValidationCheck] = Field(default_factory=list)
    rejection_reasons: List[str] = Field(default_factory=list)
    advisory_warnings: List[str] = Field(default_factory=list)


class ChemistApprovalRecord(BaseModel):
    """Immutable audit record for chemist bench trial approval."""
    approval_token: str
    candidate_id: str
    candidate_hash: str
    chemist_id: str
    chemist_name: str
    chemist_role: str
    timestamp_utc: str
    is_simulated_auth: bool = True
    approval_type: str = "BENCH_TRIAL_RELEASE"
    experimental_acknowledgement_given: bool = False
    approval_notes: str
    validation_status_at_approval: str
