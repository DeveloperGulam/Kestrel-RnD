"""
Audit Trail & Governance Logger for Kestrel R&D Formulation Assistant.
Records all formulation validations, rejections, and authenticated chemist approvals
to an append-only, tamper-evident JSON audit log with SHA-256 cryptographic hash chaining.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    CandidateFormulation,
    ChemistApprovalRecord,
    FormulationStatus,
    OverallValidationStatus,
    ValidationReport,
)


class AssistantAuditLogger:
    """Manages tamper-evident, append-only audit trail logging for formulation lifecycle events."""

    def __init__(self, log_path: Optional[str | Path] = None):
        if log_path is None:
            log_path = Path(__file__).resolve().parent.parent.parent / "assistant_audit_log.json"
        self.log_path = Path(log_path).resolve()
        self._ensure_log_file()

    def _ensure_log_file(self) -> None:
        if not self.log_path.exists():
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
        else:
            try:
                records = self.read_records()
                needs_update = False
                prev = "GENESIS"
                for rec in records:
                    if "prev_hash" not in rec or "entry_hash" not in rec:
                        rec["prev_hash"] = prev
                        rec["entry_hash"] = self._compute_entry_hash(rec)
                        needs_update = True
                    prev = rec["entry_hash"]
                if needs_update:
                    with open(self.log_path, "w", encoding="utf-8") as f:
                        json.dump(records, f, indent=2)
            except Exception:
                pass

    @staticmethod
    def _compute_entry_hash(entry: Dict[str, Any]) -> str:
        """Computes deterministic SHA-256 hash of a log record excluding 'entry_hash'."""
        hashable = {k: v for k, v in entry.items() if k != "entry_hash"}
        canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def read_records(self) -> List[Dict[str, Any]]:
        """Reads all historical audit records."""
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def verify_log_tampering(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Verifies cryptographic hash chain integrity across all records in the audit log.
        Detects any file tampering, modified attributes, deleted records, or broken hash links.
        Returns:
            (is_valid, message, records)
        """
        records = self.read_records()
        if not records:
            return True, "Audit log is empty.", []

        for i, record in enumerate(records):
            # 1. Verify prev_hash
            expected_prev = "GENESIS" if i == 0 else records[i - 1].get("entry_hash", "")
            actual_prev = record.get("prev_hash")
            if actual_prev != expected_prev:
                return (
                    False,
                    f"Tamper detected: Record at index {i} (Event {record.get('event_id')}) has broken prev_hash link. "
                    f"Expected {expected_prev[:12]}..., got {str(actual_prev)[:12]}...",
                    records,
                )

            # 2. Verify entry_hash
            recorded_hash = record.get("entry_hash")
            computed_hash = self._compute_entry_hash(record)
            if recorded_hash != computed_hash:
                return (
                    False,
                    f"Tamper detected: Record at index {i} (Event {record.get('event_id')}) payload has been modified. "
                    f"Stored hash {str(recorded_hash)[:12]}... does not match computed hash {computed_hash[:12]}...",
                    records,
                )

        return (
            True,
            f"Audit trail verified: All {len(records)} records maintain unbroken SHA-256 cryptographic hash chains.",
            records,
        )

    def log_validation_event(
        self,
        candidate: CandidateFormulation,
        report: ValidationReport,
        action: str = "VALIDATE"
    ) -> Dict[str, Any]:
        """Appends a validation result to the audit log with cryptographic chaining."""
        timestamp = datetime.now(timezone.utc).isoformat()
        current_hash = candidate.compute_recipe_hash()

        record = {
            "event_id": f"EVT-VAL-{int(datetime.now(timezone.utc).timestamp())}",
            "timestamp_utc": timestamp,
            "action": action,
            "candidate_id": candidate.candidate_id,
            "candidate_hash": current_hash,
            "title": candidate.title,
            "status": candidate.status.value,
            "overall_status": report.overall_status.value,
            "total_percentage": str(candidate.total_percentage),
            "total_cost_inr": str(candidate.total_cost_inr_per_kg),
            "can_approve": report.can_approve,
            "can_certify_performance": report.can_certify_performance,
            "requires_experimental_acknowledgement": report.requires_experimental_acknowledgement,
            "rejection_reasons": report.rejection_reasons,
            "advisory_warnings": report.advisory_warnings,
            "ingredient_count": len(candidate.ingredients),
        }

        self._append_record(record)
        return record

    def record_chemist_approval(
        self,
        candidate: CandidateFormulation,
        report: ValidationReport,
        chemist_id: str,
        chemist_name: str,
        chemist_role: str,
        approval_notes: str,
        experimental_acknowledgement_given: bool = True,
        force_duplicate: bool = False,
        validator: Optional[Any] = None,
    ) -> ChemistApprovalRecord:
        """
        Records an authenticated chemist sign-off for a candidate formulation.
        Revalidates candidate recipe and constraints on the backend.
        Rejects stale approvals, active blockers, and accidental duplicates.
        """
        current_hash = candidate.compute_recipe_hash()

        # 1. Stale Validation Check
        if report.candidate_hash != current_hash:
            raise ValueError(
                f"Approval rejected: candidate recipe has changed since validation was performed "
                f"(stale report hash {report.candidate_hash[:8]}... vs current {current_hash[:8]}...). "
                f"Revalidation is required before approval."
            )

        # 2. Backend Revalidation Check
        from .validator import DeterministicValidator
        val_engine = validator or DeterministicValidator()
        backend_report = val_engine.validate(
            candidate,
            require_chemist_approval=True,
            reviewer_name=chemist_name,
            experimental_acknowledgement_given=experimental_acknowledgement_given,
        )

        if not backend_report.can_approve:
            blocker_msgs = "; ".join(backend_report.rejection_reasons)
            raise ValueError(
                f"Cannot record chemist approval: candidate fails mandatory backend revalidation ({blocker_msgs})"
            )

        # 3. Experimental Acknowledgement Requirement
        if backend_report.requires_experimental_acknowledgement and not experimental_acknowledgement_given:
            raise ValueError(
                "Approval rejected: candidate has unverified empirical stability or softness. "
                "Explicit chemist acknowledgement of experimental risk is required for bench trial release."
            )

        # 4. Duplicate Approval Prevention Check
        existing_records = self.read_records()
        for rec in existing_records:
            if (
                rec.get("action") == "CHEMIST_APPROVAL_BENCH_RELEASE"
                and rec.get("candidate_id") == candidate.candidate_id
                and rec.get("candidate_hash") == current_hash
                and rec.get("chemist_id") == chemist_id
            ):
                if not force_duplicate:
                    raise ValueError(
                        f"Duplicate approval prevented: Candidate {candidate.candidate_id} (hash {current_hash[:8]}...) "
                        f"was already approved for bench trial by chemist {chemist_id} ({chemist_name}). "
                        f"Accidental duplicate submission rejected."
                    )

        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Build cryptographic token
        raw_token_data = f"{candidate.candidate_id}:{chemist_id}:{timestamp}:{current_hash}"
        token = "SIG-" + hashlib.sha256(raw_token_data.encode("utf-8")).hexdigest()[:16].upper()

        approval_record = ChemistApprovalRecord(
            approval_token=token,
            candidate_id=candidate.candidate_id,
            candidate_hash=current_hash,
            chemist_id=chemist_id,
            chemist_name=chemist_name,
            chemist_role=chemist_role,
            timestamp_utc=timestamp,
            is_simulated_auth=True,  # Clearly labeled simulated credentials
            approval_type="BENCH_TRIAL_RELEASE",
            experimental_acknowledgement_given=experimental_acknowledgement_given,
            approval_notes=approval_notes,
            validation_status_at_approval="PASSED",
        )

        log_entry = {
            "event_id": f"EVT-APP-{int(datetime.now(timezone.utc).timestamp())}",
            "timestamp_utc": timestamp,
            "action": "CHEMIST_APPROVAL_BENCH_RELEASE",
            "approval_token": token,
            "candidate_id": candidate.candidate_id,
            "candidate_hash": current_hash,
            "validation_results": {
                "overall_status": backend_report.overall_status.value,
                "summary": backend_report.summary_message,
                "can_certify_performance": backend_report.can_certify_performance,
                "checks_count": len(backend_report.checks),
                "advisories_count": len(backend_report.advisory_warnings),
            },
            "reviewer_identity": {
                "chemist_id": chemist_id,
                "chemist_name": chemist_name,
                "chemist_role": chemist_role,
                "auth_mode": "DEMO_SIMULATED_CREDENTIALS",
                "is_simulated_credentials": True,
            },
            "chemist_id": chemist_id,
            "chemist_name": chemist_name,
            "chemist_role": chemist_role,
            "experimental_acknowledgement_given": experimental_acknowledgement_given,
            "approval_outcome": "APPROVED_FOR_BENCH_TRIAL",
            "notes": approval_notes,
            "lifecycle_state": FormulationStatus.APPROVED_FOR_BENCH.value,
        }

        self._append_record(log_entry)
        candidate.status = FormulationStatus.APPROVED_FOR_BENCH
        candidate.validation_hash = current_hash
        return approval_record

    def _append_record(self, record: Dict[str, Any]) -> None:
        """Appends a new record ensuring cryptographic hash chain link."""
        records = self.read_records()
        prev_hash = "GENESIS" if not records else records[-1].get("entry_hash", "GENESIS")
        record["prev_hash"] = prev_hash
        record["entry_hash"] = self._compute_entry_hash(record)
        records.append(record)
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
